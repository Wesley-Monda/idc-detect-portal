import os
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi.security import OAuth2PasswordBearer
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session
from . import models, schemas, database

def mask_value(val: str) -> str:
    if not val: return "NONE"
    if len(val) < 10: return "****"
    return f"{val[:5]}...{val[-5:]}"

# SECRET_KEY management - CRITICAL for Vercel
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

# Startup validation for Vercel logs
is_vercel = os.getenv("VERCEL") == "1"
if not SECRET_KEY:
    if is_vercel:
        print("CRITICAL: SECRET_KEY environment variable is MISSING on Vercel!")
        # We don't raise ValueError here yet, but will stay alert in logs
    else:
        SECRET_KEY = "supersecretkeyformdicalaiportal"
        print("INFO: Using default local SECRET_KEY")
else:
    print(f"STARTUP: SECRET_KEY loaded (masked): {mask_value(SECRET_KEY)} (len: {len(SECRET_KEY)})")
    if is_vercel and len(SECRET_KEY) < 32:
        print("WARNING: SECRET_KEY is too short (< 32 chars)!")

pwd_context = CryptContext(schemes=["argon2", "bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(database.get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        print(f"DEBUG: Decode attempt with token: {mask_value(token)}")
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        print(f"DEBUG: Decode SUCCESS. Payload sub: {payload.get('sub')}")
        
        username: str = payload.get("sub")
        role: str = payload.get("role")
        if username is None:
            print("DEBUG: Username missing in token payload")
            raise credentials_exception
        token_data = schemas.TokenData(username=username, role=role)
    except JWTError as e:
        print(f"DEBUG: JWT Decode FAILED. Error: {type(e).__name__} - {str(e)}")
        # If it's a signature mismatch, it means SECRET_KEY differs between login and validation
        raise credentials_exception
    
    user = db.query(models.User).filter(models.User.username == token_data.username).first()
    if user is None:
        print(f"DEBUG: User '{token_data.username}' found in token but NOT in DB")
        # Log DB count to see if DB reset
        user_count = db.query(models.User).count()
        print(f"DEBUG: Current DB user count: {user_count}")
        raise credentials_exception
        
    return user
