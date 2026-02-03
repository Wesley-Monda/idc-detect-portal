from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class UserBase(BaseModel):
    username: str

class UserCreate(UserBase):
    password: str
    role: str = "patient"

class UserOut(UserBase):
    id: int
    role: str
    class Config:
        from_attributes = True

class PredictionBase(BaseModel):
    image_path: str
    result_class: int
    confidence: float

class PredictionCreate(PredictionBase):
    pass

class PredictionOut(PredictionBase):
    id: int
    created_at: datetime
    notes: Optional[str] = None
    status: str
    
    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None
    role: Optional[str] = None
