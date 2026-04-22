from typing import Generator

from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy.orm import Session

from core.config import settings
from repo.db import SessionLocal
from repo.patient_repository import PatientRepository
from repo.sql_models import User
from services.patient_service import PatientService
from services.test_history_service import TestHistoryService

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_patient_service(db: Session = Depends(get_db)) -> PatientService:
    return PatientService(PatientRepository(db), db)


def get_test_history_service(db: Session = Depends(get_db)) -> TestHistoryService:
    return TestHistoryService(db)


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")

    user = db.query(User).filter_by(username=username).first()
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")
    return user
