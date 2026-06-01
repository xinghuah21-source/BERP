from pydantic import BaseModel, ConfigDict, Field
from uuid import UUID
from typing import Literal, Optional
from datetime import datetime

class UserBase(BaseModel):
    username: str
    role: str = "student"
    grade: int = 1

class UserCreate(UserBase):
    password: str

class UserLogin(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str


class UserProfile(BaseModel):
    id: UUID
    username: str
    role: str
    grade: int
    is_baseline_calibrated: bool
    baseline_arousal: Optional[float] = None
    baseline_valence: Optional[float] = None
    baseline_calibrated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class UserBaselineResponse(BaseModel):
    is_calibrated: bool
    baseline_arousal: Optional[float] = None
    baseline_valence: Optional[float] = None
    baseline_calibrated_at: Optional[datetime] = None


class UserBaselineUpdate(BaseModel):
    baseline_arousal: float = Field(ge=0.0, le=1.0)
    baseline_valence: float = Field(ge=0.0, le=1.0)


class UserBaselineCalibrateRequest(BaseModel):
    audio_base64: str
    sample_text: str
    language: str = "zh"


class UserBaselineCalibrateResponse(UserBaselineResponse):
    sample_text: str
    audio_quality: Optional[dict] = None

class TaskResponse(BaseModel):
    id: UUID
    title: str
    content: str
    content_type: str
    difficulty: str
    grade_level: int

    model_config = ConfigDict(from_attributes=True)

class CustomTaskBase(BaseModel):
    title: str
    content: str
    language: Literal["zh", "en"]
    content_type: Literal["poetry", "prose", "essay", "custom"] = "custom"

class CustomTaskCreate(CustomTaskBase):
    pass

class CustomTaskUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    language: Optional[Literal["zh", "en"]] = None
    content_type: Optional[Literal["poetry", "prose", "essay", "custom"]] = None

class CustomTaskResponse(CustomTaskBase):
    id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CustomTaskVoiceInputRequest(BaseModel):
    audio_base64: str
    language: str = "zh"


class CustomTaskVoiceInputResponse(BaseModel):
    transcript: str
