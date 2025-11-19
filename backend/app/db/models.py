# backend/app/db/models.py
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Float
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime

Base = declarative_base()

class Student(Base):
    __tablename__ = "students"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    roll = Column(String(64), unique=True, index=True, nullable=False)   # or student id
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    encodings = relationship("FaceEncoding", back_populates="student", cascade="all, delete-orphan")
    attendance_logs = relationship("AttendanceLog", back_populates="student")

class FaceEncoding(Base):
    __tablename__ = "face_encodings"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    encoding = Column(String(2000), nullable=False)  # store as base64 or JSON string
    created_at = Column(DateTime, default=datetime.utcnow)

    student = relationship("Student", back_populates="encodings")

class AttendanceLog(Base):
    __tablename__ = "attendance_logs"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False, index=True)
    subject = Column(String(128), nullable=True)
    class_date = Column(DateTime, nullable=False)
    entry_time = Column(DateTime, nullable=False)
    exit_time = Column(DateTime, nullable=True)
    present = Column(Boolean, default=False)
    presence_score = Column(Float, default=0.0)  # e.g., fraction of lecture present

    student = relationship("Student", back_populates="attendance_logs")
