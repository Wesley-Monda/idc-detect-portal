from fastapi import APIRouter, Depends, Request, Form, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from .. import database, models, auth

router = APIRouter(
    prefix="/pathologist",
    tags=["Pathologist"]
)

templates = Jinja2Templates(directory="templates")

async def get_current_user_from_cookie(request: Request, db: Session = Depends(database.get_db)):
    # 1. Try Cookie (Raw Token)
    token = request.cookies.get("access_token")
    if token:
        token = token.strip('"')
        if token.startswith("Bearer "):
            token = token.split(" ")[1]
            
        try:
             return await auth.get_current_user(token=token, db=db)
        except Exception as e:
             print(f"DEBUG: Pathologist Cookie Invalid: {e}")

    # 2. Try Header (Bearer Token)
    auth_header = request.headers.get("Authorization")
    if auth_header:
        token = auth_header.replace("Bearer ", "").strip()
        try:
            return await auth.get_current_user(token=token, db=db)
        except:
            pass
            
    # print("DEBUG: Pathologist: Not authenticated")
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    user: models.User = Depends(get_current_user_from_cookie),
    db: Session = Depends(database.get_db)
):
    print(f"User role: {user.role}") # DEBUG LOG
    
    # Case-insensitive role check
    if user.role.lower() != "pathologist":
        return RedirectResponse(url="/login")
    
    # Get all predictions
    predictions = db.query(models.Prediction).join(models.User).order_by(models.Prediction.timestamp.desc()).all()
    
    return templates.TemplateResponse("pathologist_dashboard.html", {
        "request": request, 
        "user": user, 
        "predictions": predictions
    })

@router.get("/cases", response_class=HTMLResponse)
async def manage_cases(
    request: Request,
    user: models.User = Depends(get_current_user_from_cookie),
    db: Session = Depends(database.get_db)
):
    if user.role.lower() != "pathologist":
        return RedirectResponse(url="/login")
        
    predictions = db.query(models.Prediction).join(models.User).order_by(models.Prediction.timestamp.desc()).all()
    
    return templates.TemplateResponse("pathologist_cases.html", {
        "request": request, 
        "user": user, 
        "predictions": predictions
    })

@router.post("/review/{prediction_id}")
async def review_prediction(
    prediction_id: int,
    action: str = Form(...), # "Approve", "Reject", "Save Note"
    notes: str = Form(None),
    user: models.User = Depends(get_current_user_from_cookie),
    db: Session = Depends(database.get_db)
):
    # Debug logging
    print(f"DEBUG: Reviewing user role: {user.role}")
    
    if user.role.lower() != "pathologist":
        print(f"DEBUG: Authorization failed for role: {user.role}")
        raise HTTPException(status_code=403, detail="Not authorized")
        
    prediction = db.query(models.Prediction).filter(models.Prediction.id == prediction_id).first()
    if prediction:
        if action == "Approve":
            prediction.status = "Approved"
        elif action == "Reject":
            prediction.status = "Rejected"
        
        # Always update notes if provided
        await db.refresh(prediction) # Ensure fresh stats? No need.
        if notes:
            prediction.notes = notes
            
        db.commit()
    
    # Redirect back to Cases list
    return RedirectResponse(url="/pathologist/cases", status_code=status.HTTP_302_FOUND)

@router.get("/export")
async def export_predictions_csv(
    user: models.User = Depends(get_current_user_from_cookie),
    db: Session = Depends(database.get_db)
):
    # Authorization Log
    print(f"DEBUG: Exporting data for user role: {user.role}")
    
    if user.role.lower() != "pathologist":
        raise HTTPException(status_code=403, detail="Not authorized")
        
    predictions = db.query(models.Prediction).join(models.User).order_by(models.Prediction.timestamp.desc()).all()
    
    import csv
    import io
    from fastapi.responses import StreamingResponse
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Header
    writer.writerow(["ID", "Date", "Patient ID", "Image Path", "Prediction", "Confidence", "Status", "Notes"])
    
    # Rows
    for pred in predictions:
        pred_label = "IDC Positive" if pred.result_class == 1 else "Negative"
        writer.writerow([
            pred.id,
            pred.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            pred.user_id,
            pred.image_path,
            pred_label,
            f"{pred.confidence:.4f}",
            pred.status,
            pred.notes or ""
        ])
        
    output.seek(0)
    
    response = StreamingResponse(iter([output.getvalue()]), media_type="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=idc_predictions_export.csv"
    return response
