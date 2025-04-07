from contextlib import asynccontextmanager

import bcrypt
import uuid

from fastapi import FastAPI, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from db import SessionLocal, engine
from models import (
    Base,
    Prospect,
    Resume,
    Attorney,
    ProspectCreate,
    ProspectOut,
    UpdateFirstName,
    UpdateLastName,
    UpdateResume,
    ProspectSubmit,
    AdminProspectMark
)
from email_utils import send_email
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import EmailStr
from datetime import datetime, timezone
import random

@asynccontextmanager
async def lifespan(app: FastAPI):
    print('Starting lifespan')
    Base.metadata.create_all(bind=engine)

    session = SessionLocal()
    now = datetime.now(timezone.utc)

    default_attorneys = [
        {
            "name": "Alex Morgan",
            "email": "hello@example.com",
            "password": "pw1",
        }    
    ]

    for a in default_attorneys:
        exists = session.query(Attorney).filter_by(email=a["email"]).first()
        if not exists:
            hashed_pw = bcrypt.hashpw(a["password"].encode(), bcrypt.gensalt()).decode()
            session.add(Attorney(
                id=str(uuid.uuid4()),
                name=a["name"],
                email=a["email"],
                salted_hashed_password=hashed_pw,
                created_at=now,
                updated_at=now
            ))

    session.commit()
    session.close()

    yield

app = FastAPI(lifespan=lifespan)

security = HTTPBasic()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def verify_attorney(
        credentials: HTTPBasicCredentials = Depends(security),
        db: Session = Depends(get_db)
):
    attorney = db.query(Attorney).filter_by(email=credentials.username).first()
    if not attorney or not bcrypt.checkpw(credentials.password.encode(), attorney.salted_hashed_password.encode()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return attorney

@app.get("/")
def root():
    return {"status": "ok"}

@app.post("/prospect/", status_code=201)
def create_prospect(data: ProspectCreate, db: Session = Depends(get_db)):
    email = data.email.lower()
    existing = db.query(Prospect).filter_by(email=email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Prospect already exists or has been submitted.")

    now = datetime.now(timezone.utc)
    resume = Resume(resume_data=data.resume.strip(), created_at=now, updated_at=now)
    db.add(resume)
    db.flush()

    prospect = Prospect(
        first_name=data.first_name.strip(),
        last_name=data.last_name.strip(),
        email=email,
        resume=resume,
        state="CREATED",
        created_at=now,
        updated_at=now,
    )
    db.add(prospect)
    db.commit()
    return {"message": "Prospect created."}

@app.get("/prospect/{email}", response_model=ProspectOut)
def get_prospect(email: EmailStr, db: Session = Depends(get_db)):
    email = email.lower()
    prospect = db.query(Prospect).join(Resume).filter(Prospect.email == email).order_by(Prospect.updated_at.desc()).first()
    if not prospect:
        raise HTTPException(status_code=404, detail="Prospect not found")

    return ProspectOut(
        first_name=prospect.first_name,
        last_name=prospect.last_name,
        email=prospect.email,
        resume=prospect.resume.resume_data,
    )

@app.put("/prospect/first-name")
def update_first_name(data: UpdateFirstName, db: Session = Depends(get_db)):
    prospect = db.query(Prospect).filter_by(email=data.email.lower()).first()
    if not prospect or prospect.state != "CREATED":
        raise HTTPException(status_code=400, detail="Prospect cannot be edited")

    prospect.first_name = data.first_name.strip()
    prospect.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {"message": "First name updated."}

@app.put("/prospect/last-name")
def update_last_name(data: UpdateLastName, db: Session = Depends(get_db)):
    prospect = db.query(Prospect).filter_by(email=data.email.lower()).first()
    if not prospect or prospect.state != "CREATED":
        raise HTTPException(status_code=400, detail="Prospect cannot be edited")

    prospect.last_name = data.last_name.strip()
    prospect.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {"message": "Last name updated."}

@app.put("/prospect/resume")
def update_resume(data: UpdateResume, db: Session = Depends(get_db)):
    prospect = db.query(Prospect).join(Resume).filter(Prospect.email == data.email.lower()).first()
    if not prospect or prospect.state != "CREATED":
        raise HTTPException(status_code=400, detail="Prospect cannot be edited")

    prospect.resume.resume_data = data.resume.strip()
    prospect.resume.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {"message": "Resume updated."}

@app.put("/prospect/submit")
def submit_prospect(data: ProspectSubmit, db: Session = Depends(get_db)):
    email = data.email.lower()
    prospect = db.query(Prospect).filter_by(email=email).first()
    if not prospect or prospect.state != "CREATED":
        raise HTTPException(status_code=400, detail="Prospect cannot be submitted")

    attorneys = db.query(Attorney).all()
    if not attorneys:
        raise HTTPException(status_code=500, detail="No attorneys available")
    attorney = random.choice(attorneys)

    now = datetime.now(timezone.utc)
    prospect.state = "PENDING"
    prospect.updated_at = now
    db.commit()

    subject = "New Prospect Submission"
    body = f"""
Hey {prospect.first_name} {prospect.last_name},
Thanks for submitting your info to Alma. One of our attorneys will be in touch soon.
In the meantime, your assigned attorney is {attorney.name} ({attorney.email}).
""".strip()

    try:
        send_email(subject, body, [prospect.email, attorney.email])
    except Exception:
        print("Logging that email error occurred")
        pass

    return {"message": "Prospect submitted."}

@app.post("/admin/prospect/mark")
def mark_prospect(data: AdminProspectMark, db: Session = Depends(get_db), attorney=Depends(verify_attorney)):
    prospect = db.query(Prospect).filter_by(email=data.email.lower()).first()
    if not prospect or prospect.state != "PENDING":
        raise HTTPException(status_code=400, detail="Only PENDING prospects can be marked")

    prospect.state = "REACHED_OUT"
    prospect.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {"message": "Prospect marked as reached out."}

@app.get("/admin/prospect/")
def list_prospects(
        db: Session = Depends(get_db),
        attorney = Depends(verify_attorney),
        limit: int = Query(5, ge=1, le=100),
        offset: int = Query(0, ge=0)
):
    prospects = (
        db.query(Prospect)
        .join(Resume)
        .order_by(Prospect.updated_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return [
        {
            "first_name": p.first_name,
            "last_name": p.last_name,
            "email": p.email,
            "state": p.state,
            "resume": p.resume.resume_data,
        }
        for p in prospects
    ]
