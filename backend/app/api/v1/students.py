from typing import List
import json

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db import models

router = APIRouter(prefix="/api/v1/students", tags=["students"])

# -----------------------------
# SCHEMAS
# -----------------------------
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


class FaceEnroll(BaseModel):
    student_id: int
    embedding: List[float]


# -----------------------------
# CREATE STUDENT
# -----------------------------
@router.post("/", response_model=StudentOut, status_code=status.HTTP_201_CREATED)
async def create_student(payload: StudentCreate, db: AsyncSession = Depends(get_db)):
    q = await db.execute(select(models.Student).where(models.Student.roll == payload.roll))
    existing = q.scalars().first()
    if existing:
        raise HTTPException(400, "Student with this roll already exists")

    student = models.Student(
        roll=payload.roll,
        name=payload.name,
        email=payload.email
    )
    db.add(student)
    await db.commit()
    await db.refresh(student)
    return student


# -----------------------------
# LIST STUDENTS
# -----------------------------
@router.get("/", response_model=List[StudentOut])
async def list_students(db: AsyncSession = Depends(get_db)):
    q = await db.execute(select(models.Student))
    return q.scalars().all()


# -----------------------------
# GET ALL FACE ENCODINGS (NEW)
# -----------------------------
@router.get("/encodings")
async def students_encodings(db: AsyncSession = Depends(get_db)):
    stmt = select(models.Student)
    res = await db.execute(stmt)
    students = res.scalars().all()

    out = []
    for s in students:
        emb = None
        if s.face_embedding:
            try:
                emb = json.loads(s.face_embedding)
            except:
                emb = None

        out.append({
            "id": s.id,
            "roll": s.roll,
            "name": s.name,
            "face_embedding": emb
        })

    return out


# -----------------------------
# GET SINGLE STUDENT
# -----------------------------
@router.get("/{student_id}", response_model=StudentOut)
async def get_student(student_id: int, db: AsyncSession = Depends(get_db)):
    q = await db.execute(select(models.Student).where(models.Student.id == student_id))
    student = q.scalars().first()
    if not student:
        raise HTTPException(404, "Student not found")
    return student


# -----------------------------
# REGISTER FACE
# -----------------------------
@router.post("/register-face")
async def register_face(payload: FaceEnroll, db: AsyncSession = Depends(get_db)):
    q = await db.execute(select(models.Student).where(models.Student.id == payload.student_id))
    student = q.scalars().first()
    if not student:
        raise HTTPException(404, "Student not found")

    if not payload.embedding:
        raise HTTPException(400, "Embedding must not be empty")

    emb_json = json.dumps(payload.embedding)

    stmt = (
        update(models.Student)
        .where(models.Student.id == payload.student_id)
        .values(face_embedding=emb_json)
    )

    await db.execute(stmt)
    await db.commit()

    return {"status": "success", "message": "Face registered successfully"}
