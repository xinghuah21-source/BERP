from typing import List, Optional, Annotated
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from .database import get_db
from .models import Task, User
from .schemas import TaskResponse
from .auth import get_current_user

router = APIRouter(prefix="/tasks", tags=["tasks"])

@router.get("", response_model=List[TaskResponse])
async def get_tasks(
    grade: Optional[int] = None,
    difficulty: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = select(Task)
    if grade:
        query = query.where(Task.grade_level == grade)
    if difficulty:
        query = query.where(Task.difficulty == difficulty)
    
    result = await db.execute(query)
    return result.scalars().all()

@router.get("/{id}", response_model=TaskResponse)
async def get_task(
    id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(select(Task).where(Task.id == id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task
