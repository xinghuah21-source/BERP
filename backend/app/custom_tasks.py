from datetime import datetime
from typing import List
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from .auth import get_current_user
from .database import get_db
from .models import CustomTask, User
from .schemas import (
    CustomTaskCreate,
    CustomTaskResponse,
    CustomTaskUpdate,
    CustomTaskVoiceInputRequest,
    CustomTaskVoiceInputResponse,
)


router = APIRouter(prefix="", tags=["custom-tasks"])
CUSTOM_TASK_VOICE_TIMEOUT_SECONDS = 60.0


@router.get("/custom-tasks", response_model=List[CustomTaskResponse])
async def list_my_custom_tasks(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(CustomTask).where(CustomTask.user_id == current_user.id).order_by(CustomTask.updated_at.desc()))
    return result.scalars().all()


@router.get("/custom-tasks/{task_id}", response_model=CustomTaskResponse)
async def get_custom_task(
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(CustomTask).where(CustomTask.id == task_id))
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Task not found")
    if row.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    return row


@router.post("/custom-tasks", response_model=CustomTaskResponse)
async def create_custom_task(
    task: CustomTaskCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    new_task = CustomTask(
        user_id=current_user.id,
        title=task.title,
        content=task.content,
        language=task.language,
        content_type=task.content_type,
    )
    db.add(new_task)
    await db.commit()
    await db.refresh(new_task)
    return new_task


@router.put("/custom-tasks/{task_id}", response_model=CustomTaskResponse)
async def update_custom_task(
    task_id: UUID,
    task: CustomTaskUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(CustomTask).where(CustomTask.id == task_id))
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Task not found")
    if row.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden")

    if task.title is not None:
        row.title = task.title
    if task.content is not None:
        row.content = task.content
    if task.language is not None:
        row.language = task.language
    if task.content_type is not None:
        row.content_type = task.content_type
    row.updated_at = datetime.utcnow()

    await db.commit()
    await db.refresh(row)
    return row


@router.delete("/custom-tasks/{task_id}")
async def delete_custom_task(
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(CustomTask).where(CustomTask.id == task_id))
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Task not found")
    if row.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden")

    await db.delete(row)
    await db.commit()
    return {"status": "ok"}


@router.post("/custom-tasks/voice-input", response_model=CustomTaskVoiceInputResponse)
async def custom_task_voice_input(
    payload: CustomTaskVoiceInputRequest,
    current_user: User = Depends(get_current_user),
):
    ai_url = f"{settings.AI_ENGINE_BASE_URL.rstrip('/')}/evaluate"
    try:
        async with httpx.AsyncClient(timeout=CUSTOM_TASK_VOICE_TIMEOUT_SECONDS, trust_env=False) as client:
            resp = await client.post(
                ai_url,
                json={
                    "audio_base64": payload.audio_base64,
                    "standard_text": "",
                    "language": payload.language,
                },
            )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Voice input failed: {exc}")

    transcript = str(data.get("transcript") or "").strip()
    if not transcript:
        raise HTTPException(status_code=422, detail="识别失败，请手动输入或重试")
    return CustomTaskVoiceInputResponse(transcript=transcript)
