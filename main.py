import uuid
from datetime import datetime, timezone
from db import SessionLocal, engine
from models import Base, Attorney

Base.metadata.create_all(bind=engine)

def insert_attorneys():
    now = datetime.now(timezone.utc)
    session = SessionLocal()

    attorneys = [
        Attorney(
            id=str(uuid.uuid4()),
            name="Alex Morgan",
            email="a@example.com",
            salted_hashed_password="hashed_pw_1",
            created_at=now,
            updated_at=now,
        ),
        Attorney(
            id=str(uuid.uuid4()),
            name="Jamie Lee",
            email="b@example.com",
            salted_hashed_password="hashed_pw_2",
            created_at=now,
            updated_at=now,
        ),
    ]

    for attorney in attorneys:
        exists = session.query(Attorney).filter_by(email=attorney.email).first()
        if not exists:
            session.add(attorney)

    session.commit()
    session.close()

if __name__ == "__main__":
    insert_attorneys()
