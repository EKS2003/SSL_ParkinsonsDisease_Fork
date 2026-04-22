from datetime import datetime, timedelta

from jose import jwt
from passlib.context import CryptContext

from core.config import settings
from repo.db import SessionLocal
from repo.sql_models import User

pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")


def authenticate(username: str, password: str) -> User | None:
    try:
        with SessionLocal() as session:
            user = session.query(User).filter_by(username=username).first()
            if user and pwd.verify(password, user.hashed_password):
                return user
    except Exception:
        return None


def create_access_token(sub: str) -> str:
    to_encode = {
        "sub": sub,
        "exp": datetime.now() + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(to_encode, settings.secret_key, algorithm="HS256")
