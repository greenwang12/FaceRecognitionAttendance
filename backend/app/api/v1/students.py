# backend/app/api/v1/students.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from pydantic import BaseModel

from app.db.session import get_db
from app.db import models

router = APIRouter(prefix="/api/v1/students", tags=["students"])

class StudentCreate(BaseModel):
    roll: str
    name: str
    email: str | None = None

class StudentOut(BaseModel):
    id: int
    roll: str
    name: str
    email: str | None

    model_config = {"from_attributes": True}

@router.post("/", response_model=StudentOut, status_code=status.HTTP_201_CREATED)
async def create_student(payload: StudentCreate, db: AsyncSession = Depends(get_db)):
    # Use ORM select to check duplicates
    q = await db.execute(select(models.Student).where(models.Student.roll == payload.roll))
    existing = q.scalars().first()
    if existing:
        raise HTTPException(status_code=400, detail="Student with this roll exists")
    student = models.Student(roll=payload.roll, name=payload.name, email=payload.email)
    db.add(student)
    await db.commit()
    await db.refresh(student)
    return student

@router.get("/", response_model=List[StudentOut])
async def list_students(db: AsyncSession = Depends(get_db)):
    q = await db.execute(select(models.Student))
    rows = q.scalars().all()   # now returns mapped Student objects
    return rows

@router.get("/{student_id}", response_model=StudentOut)
async def get_student(student_id: int, db: AsyncSession = Depends(get_db)):
    q = await db.execute(select(models.Student).where(models.Student.id == student_id))
    s = q.scalars().first()
    if not s:
        raise HTTPException(status_code=404, detail="Not found")
    return s
