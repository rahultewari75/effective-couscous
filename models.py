import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, Enum, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from db import Base
from pydantic import BaseModel, EmailStr, constr


class Resume(Base):
    __tablename__ = "resume"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    resume_data = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=datetime.now(timezone.utc))

    prospect = relationship("Prospect", back_populates="resume", uselist=False)


class Prospect(Base):
    __tablename__ = "prospect"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    email = Column(String, nullable=False, unique=True, index=True)
    resume_id = Column(String, ForeignKey("resume.id"))
    state = Column(Enum("CREATED", "PENDING", "REACHED_OUT", name="prospect_state"), nullable=False)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=datetime.now(timezone.utc))

    resume = relationship("Resume", back_populates="prospect")


class Attorney(Base):
    __tablename__ = "attorney"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    email = Column(String, nullable=False)
    salted_hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=datetime.now(timezone.utc))

class ProspectCreate(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    resume: constr(min_length=1)

class ProspectOut(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    resume: str

class UpdateFirstName(BaseModel):
    email: EmailStr
    first_name: str

class UpdateLastName(BaseModel):
    email: EmailStr
    last_name: str

class UpdateResume(BaseModel):
    email: EmailStr
    resume: str

class ProspectSubmit(BaseModel):
    email: EmailStr

class AdminProspectMark(BaseModel):
    email: EmailStr
