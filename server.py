from contextlib import asynccontextmanager
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
import secrets
import random

Base.metadata.create_all(bind=engine)

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield

app = FastAPI(lifespan=lifespan)

security = HTTPBasic()
ADMIN_USER = "admin"
ADMIN_PASS = "bigchungus"

def verify_admin(credentials: HTTPBasicCredentials = Depends(security)):
    correct_username = secrets.compare_digest(credentials.username, ADMIN_USER)
    correct_password = secrets.compare_digest(credentials.password, ADMIN_PASS)
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin credentials",
            headers={"WWW-Authenticate": "Basic"},
        )

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

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

Best,  
The Alma Team
""".strip()

    try:
        send_email(subject, body, [prospect.email, attorney.email])
    except Exception:
        pass

    return {"message": "Prospect submitted."}

@app.post("/admin/prospect/mark")
def mark_prospect(data: AdminProspectMark, db: Session = Depends(get_db), _: str = Depends(verify_admin)):
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
        _: str = Depends(verify_admin),
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
