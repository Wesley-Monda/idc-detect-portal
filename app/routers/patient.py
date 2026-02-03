from fastapi import APIRouter, Depends, UploadFile, File, Request, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import Optional
import os
import shutil
from datetime import datetime

from .. import database, models, schemas, auth, ml_utils

router = APIRouter(
    prefix="/patient",
    tags=["Patient"]
)

templates = Jinja2Templates(directory="templates")

# Dependency to get current user from cookie
async def get_current_user_from_cookie(request: Request, db: Session = Depends(database.get_db)):
    # 1. Try Cookie
    token = request.cookies.get("access_token")
    if token:
        token = token.strip('"')
        scheme, _, param = token.partition(" ")
        return await auth.get_current_user(token=param, db=db)
            
    # 2. Try Header
    auth_header = request.headers.get("Authorization")
    if auth_header:
        scheme, _, param = auth_header.partition(" ")
        if scheme.lower() == "bearer":
            return await auth.get_current_user(token=param, db=db)
            
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(
    request: Request, 
    user: models.User = Depends(get_current_user_from_cookie),
    db: Session = Depends(database.get_db)
):
    if user.role.lower() != "patient":
        return RedirectResponse(url="/login")
    
    predictions = db.query(models.Prediction).filter(models.Prediction.user_id == user.id).order_by(models.Prediction.timestamp.desc()).all()
    return templates.TemplateResponse("patient_dashboard.html", {
        "request": request, 
        "user": user, 
        "predictions": predictions
    })

@router.post("/upload")
async def upload_image(
    request: Request,
    file: UploadFile = File(...),
    user: models.User = Depends(get_current_user_from_cookie),
    db: Session = Depends(database.get_db)
):
    # Save file
    upload_dir = "static/uploads"
    if not os.path.exists(upload_dir):
        os.makedirs(upload_dir)
    
    file_location = f"{upload_dir}/{datetime.now().timestamp()}_{file.filename}"
    
    # Read file for prediction
    contents = await file.read()
    
    # Save to disk
    with open(file_location, "wb") as f:
        f.write(contents)
        
    # Run Inference
    predicted_class, confidence = ml_utils.predict(contents)
    
    # Save to DB
    new_prediction = models.Prediction(
        user_id=user.id,
        image_path=file_location,
        result_class=predicted_class,
        confidence=confidence
    )
    db.add(new_prediction)
    db.commit()
    db.refresh(new_prediction)
    
    return RedirectResponse(url=f"/patient/result/{new_prediction.id}", status_code=status.HTTP_302_FOUND)

@router.get("/result/{prediction_id}", response_class=HTMLResponse)
async def view_result(
    request: Request,
    prediction_id: int,
    user: models.User = Depends(get_current_user_from_cookie),
    db: Session = Depends(database.get_db)
):
    prediction = db.query(models.Prediction).filter(models.Prediction.id == prediction_id).first()
    if not prediction or prediction.user_id != user.id:
        return RedirectResponse(url="/patient/dashboard")
        
    return templates.TemplateResponse("result.html", {
        "request": request,
        "user": user,
        "prediction": prediction
    })

@router.get("/report/{prediction_id}")
async def download_report(
    prediction_id: int,
    user: models.User = Depends(get_current_user_from_cookie),
    db: Session = Depends(database.get_db)
):
    prediction = db.query(models.Prediction).filter(models.Prediction.id == prediction_id).first()
    if not prediction or prediction.user_id != user.id:
        raise HTTPException(status_code=404, detail="Prediction not found")
        
    # Generate simple HTML report string
    report_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>IDC Analysis Report #{prediction.id}</title>
        <style>
            body {{ font-family: sans-serif; padding: 40px; max-width: 800px; margin: 0 auto; line-height: 1.6; }}
            .header {{ border-bottom: 2px solid #333; padding-bottom: 20px; mb-10; }}
            .result-box {{ padding: 20px; background: #f0f0f0; border-radius: 8px; margin: 20px 0; }}
            .positive {{ color: #e11d48; font-weight: bold; }}
            .negative {{ color: #10b981; font-weight: bold; }}
            .disclaimer {{ margin-top: 40px; font-size: 0.8rem; color: #666; border-top: 1px solid #ccc; padding-top: 10px; }}
        </style>
    </head>
    <body onload="window.print()">
        <div class="header">
            <h1>IDC Detect Portal - Analysis Report</h1>
            <p><strong>Patient ID:</strong> {user.username}</p>
            <p><strong>Report Date:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            <p><strong>Reference ID:</strong> #{prediction.id}</p>
        </div>
        
        <div class="result-box">
            <h2>AI Prediction</h2>
            <p>Result: <span class="{'positive' if prediction.result_class == 1 else 'negative'}">
                {'POSITIVE FOR IDC' if prediction.result_class == 1 else 'NEGATIVE FOR IDC'}
            </span></p>
            <p>Confidence: <strong>{round(prediction.confidence * 100, 2)}%</strong></p>
            <p>Original Image: {prediction.image_path}</p>
        </div>
        
        <div class="disclaimer">
            <p><strong>DISCLAIMER:</strong> This is an educational tool demonstration only. 
            This report represents a prediction made by an AI model (ResNet50). 
            It is NOT a medical diagnosis. Please consult a qualified pathologist for verification.</p>
        </div>
    </body>
    </html>
    """
    
    return HTMLResponse(content=report_html, media_type="text/html")
