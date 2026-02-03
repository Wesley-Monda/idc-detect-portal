from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    role = Column(String)  # "patient" or "pathologist"

    predictions = relationship("Prediction", back_populates="owner")

class Prediction(Base):
    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    image_path = Column(String)
    result_class = Column(Integer) # 0 or 1
    confidence = Column(Float)
    notes = Column(String, nullable=True)
    status = Column(String, default="pending") # "pending", "reviewed"
    timestamp = Column(DateTime, default=datetime.utcnow)

    owner = relationship("User", back_populates="predictions")
