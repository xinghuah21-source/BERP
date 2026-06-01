from datetime import datetime, timedelta
import os
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
import httpx
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from .database import get_db
from .models import User
from .schemas import (
    Token,
    UserBaselineCalibrateRequest,
    UserBaselineCalibrateResponse,
    UserBaselineResponse,
    UserBaselineUpdate,
    UserCreate,
    UserLogin,
    UserProfile,
)
from .config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

router = APIRouter(prefix="/auth", tags=["auth"])
BASELINE_CALIBRATION_TIMEOUT_SECONDS = float(os.getenv("BASELINE_CALIBRATION_TIMEOUT_SECONDS", "60"))


def _to_profile(user: User) -> UserProfile:
    return UserProfile(
        id=user.id,
        username=user.username,
        role=user.role,
        grade=user.grade,
        is_baseline_calibrated=user.baseline_arousal is not None and user.baseline_valence is not None,
        baseline_arousal=user.baseline_arousal,
        baseline_valence=user.baseline_valence,
        baseline_calibrated_at=user.baseline_calibrated_at,
    )


def _to_baseline_response(user: User) -> UserBaselineResponse:
    return UserBaselineResponse(
        is_calibrated=user.baseline_arousal is not None and user.baseline_valence is not None,
        baseline_arousal=user.baseline_arousal,
        baseline_valence=user.baseline_valence,
        baseline_calibrated_at=user.baseline_calibrated_at,
    )

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)], db: AsyncSession = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if user is None:
        raise credentials_exception
    return user

@router.post("/register", response_model=Token)
async def register(user_in: UserCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == user_in.username))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Username already registered")
    
    new_user = User(
        username=user_in.username,
        hashed_password=get_password_hash(user_in.password),
        role=user_in.role,
        grade=user_in.grade
    )
    db.add(new_user)
    await db.commit()
    
    access_token = create_access_token(data={"sub": new_user.username})
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/login", response_model=Token)
async def login(user_in: UserLogin, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == user_in.username))
    user = result.scalar_one_or_none()
    if not user or not verify_password(user_in.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    
    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me", response_model=UserProfile)
async def me(current_user: User = Depends(get_current_user)):
    return _to_profile(current_user)


@router.get("/baseline", response_model=UserBaselineResponse)
async def get_baseline(current_user: User = Depends(get_current_user)):
    return _to_baseline_response(current_user)


@router.put("/baseline", response_model=UserBaselineResponse)
async def update_baseline(
    payload: UserBaselineUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Keep a manual update endpoint so baseline data can be corrected or imported safely.
    current_user.baseline_arousal = payload.baseline_arousal
    current_user.baseline_valence = payload.baseline_valence
    current_user.baseline_calibrated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(current_user)
    return _to_baseline_response(current_user)


@router.post("/baseline/calibrate", response_model=UserBaselineCalibrateResponse)
async def calibrate_baseline(
    payload: UserBaselineCalibrateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Reuse the existing AI engine emotion pipeline instead of duplicating signal processing in backend.
    ai_url = f"{settings.AI_ENGINE_BASE_URL.rstrip('/')}/calibrate_emotion"
    try:
        async with httpx.AsyncClient(timeout=BASELINE_CALIBRATION_TIMEOUT_SECONDS, trust_env=False) as client:
            resp = await client.post(
                ai_url,
                json={
                    "audio_base64": payload.audio_base64,
                    "standard_text": payload.sample_text,
                    "language": payload.language,
                },
            )
        resp.raise_for_status()
        data = resp.json()
        baseline_arousal = float(data["baseline_arousal"])
        baseline_valence = float(data["baseline_valence"])
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Baseline calibration failed: {exc}")

    current_user.baseline_arousal = baseline_arousal
    current_user.baseline_valence = baseline_valence
    current_user.baseline_calibrated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(current_user)

    return UserBaselineCalibrateResponse(
        is_calibrated=True,
        baseline_arousal=current_user.baseline_arousal,
        baseline_valence=current_user.baseline_valence,
        baseline_calibrated_at=current_user.baseline_calibrated_at,
        sample_text=payload.sample_text,
        audio_quality=data.get("audio_quality"),
    )
