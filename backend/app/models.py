import uuid
from sqlalchemy import String, Integer, Column, Text, DateTime, ForeignKey, Float
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from .database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, default="student") # student/teacher
    grade = Column(Integer, default=1)
    # Store each student's neutral-reading baseline for personalized emotion matching.
    baseline_arousal = Column(Float, nullable=True)
    baseline_valence = Column(Float, nullable=True)
    baseline_calibrated_at = Column(DateTime(timezone=True), nullable=True)

class Task(Base):
    __tablename__ = "tasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    content_type = Column(String) # poetry/classic/modern
    difficulty = Column(String) # easy/medium/hard
    grade_level = Column(Integer)

class CustomTask(Base):
    __tablename__ = "custom_tasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    language = Column(String, nullable=False)
    content_type = Column(String, nullable=False, default="custom")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
