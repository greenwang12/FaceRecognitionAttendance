from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Float, Text
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime

Base = declarative_base()

class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    roll = Column(String(64), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # store a primary embedding (optional) as JSON/text, and/or multiple encodings in FaceEncoding
    face_embedding = Column(Text, nullable=True)

    encodings = relationship("FaceEncoding", back_populates="student", cascade="all, delete-orphan")
    attendance_logs = relationship("AttendanceLog", back_populates="student")

    def __repr__(self):
        return f"<Student id={self.id} roll={self.roll} name={self.name}>"

class FaceEncoding(Base):
    __tablename__ = "face_encodings"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    # store encoding as JSON string (Text) to support long arrays
    encoding = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    student = relationship("Student", back_populates="encodings")

    def __repr__(self):
        return f"<FaceEncoding id={self.id} student_id={self.student_id}>"

class AttendanceLog(Base):
    __tablename__ = "attendance_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False, index=True)
    subject = Column(String(128), nullable=True)
    class_date = Column(DateTime, nullable=False)
    entry_time = Column(DateTime, nullable=False)
    exit_time = Column(DateTime, nullable=True)
    present = Column(Boolean, default=False)
    presence_score = Column(Float, default=0.0)

    student = relationship("Student", back_populates="attendance_logs")

    def __repr__(self):
        return f"<AttendanceLog id={self.id} student_id={self.student_id} present={self.present}>"
