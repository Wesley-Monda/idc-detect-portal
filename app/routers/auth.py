from fastapi import APIRouter, Depends, status, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from .. import database, models, schemas, auth

router = APIRouter(
    tags=["Authentication"]
)

templates = Jinja2Templates(directory="templates")

@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@router.post("/register")
async def register(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    role: str = Form(...), # "patient" or "pathologist"
    db: Session = Depends(database.get_db)
):
    user = db.query(models.User).filter(models.User.username == username).first()
    if user:
        return templates.TemplateResponse("register.html", {"request": request, "error": "Username already taken"})
    
    hashed_password = auth.get_password_hash(password)
    # Force role to be Title case (e.g. "Pathologist") as requested
    formatted_role = role.capitalize() 
    new_user = models.User(username=username, hashed_password=hashed_password, role=formatted_role)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@router.post("/token")
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(database.get_db)
):
    user = db.query(models.User).filter(models.User.username == username).first()
    if not user or not auth.verify_password(password, user.hashed_password):
        return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid credentials"})
    
    access_token = auth.create_access_token(data={"sub": user.username, "role": user.role})
    
    # Check if client wants JSON (API/Swagger) or HTML (Browser)
    accept = request.headers.get("accept", "")
    if "application/json" in accept:
        return {
            "access_token": access_token, 
            "token_type": "bearer",
            "role": user.role # Extra info
        }
    
    # Browser Flow: Redirect
    target_role = user.role.lower()
    response = RedirectResponse(url=f"/{target_role}/dashboard", status_code=status.HTTP_302_FOUND)
    
    # Set explicit cookie for browser (Raw token, HttpOnly for security)
    response.set_cookie(
        key="access_token", 
        value=access_token, # Raw JWT, no "Bearer " prefix in cookie to simplify parsing
        httponly=True,      # Prevent JS access (XSS protection)
        secure=False,       # Localhost (False)
        samesite="lax"
    )
    print(f"DEBUG: Login successful for {username}. Cookie set (HttpOnly).")
    return response

# ... logout ...

# --- Profile Routes ---

# Dependency Helper (re-defined here to keep auth self-contained)
async def get_current_user_from_cookie(request: Request, db: Session = Depends(database.get_db)):
    # 1. Try Cookie (Raw Token)
    token = request.cookies.get("access_token")
    if token:
        # If inadvertently quoted
        token = token.strip('"')
        # If inadvertently has Bearer prefix
        if token.startswith("Bearer "):
            token = token.split(" ")[1]
            
        try:
             user = await auth.get_current_user(token=token, db=db)
             print(f"DEBUG: Cookie Auth Success: {user.username}, Role: {user.role}")
             return user
        except Exception as e:
             print(f"DEBUG: Cookie Token Invalid: {e}")
    
    # 2. Try Header (Bearer Token)
    auth_header = request.headers.get("Authorization")
    if auth_header:
        token = auth_header.replace("Bearer ", "").strip()
        try:
            return await auth.get_current_user(token=token, db=db)
        except Exception as e:
             print(f"DEBUG: Header Auth Failed: {e}")

    print("DEBUG: No valid session found.")
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

@router.get("/profile", response_class=HTMLResponse)
async def profile_page(
    request: Request, 
    user: models.User = Depends(get_current_user_from_cookie)
):
    return templates.TemplateResponse("profile.html", {"request": request, "user": user})

@router.post("/profile/password")
async def change_password(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    user: models.User = Depends(get_current_user_from_cookie),
    db: Session = Depends(database.get_db)
):
    # Verify Current
    if not auth.verify_password(current_password, user.hashed_password):
        return templates.TemplateResponse("profile.html", {"request": request, "user": user, "error": "Incorrect current password"})
    
    # Verify New
    if new_password != confirm_password:
        return templates.TemplateResponse("profile.html", {"request": request, "user": user, "error": "New passwords do not match"})
        
    # Update
    user.hashed_password = auth.get_password_hash(new_password)
    db.commit()
    
    return templates.TemplateResponse("profile.html", {"request": request, "user": user, "success": "Password updated successfully"})

@router.post("/profile/delete")
async def delete_account(
    request: Request,
    confirmation: str = Form(...),
    user: models.User = Depends(get_current_user_from_cookie),
    db: Session = Depends(database.get_db)
):
    if confirmation != "DELETE":
        return templates.TemplateResponse("profile.html", {"request": request, "user": user, "error": "Type DELETE to confirm"})
        
    # Delete associated data first? (Cascading usually handles this if set up, otherwise manual)
    # SQLAlchemy default is usually SET NULL or nothing unless Cascade is ON.
    # We will just delete the user, assuming simple setup.
    db.query(models.Prediction).filter(models.Prediction.user_id == user.id).delete()
    db.delete(user)
    db.commit()
    
    response = RedirectResponse(url="/register?msg=Account+deleted", status_code=status.HTTP_302_FOUND)
    response.delete_cookie("access_token")
    return response
