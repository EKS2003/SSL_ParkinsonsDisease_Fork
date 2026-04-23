from datetime import datetime, timedelta, timezone

import bcrypt
from jose import jwt

from core.config import settings
from repo.db import SessionLocal
from repo.sql_models import User


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


def authenticate(username: str, password: str) -> User | None:
    try:
        with SessionLocal() as session:
            user = session.query(User).filter_by(username=username).first()
            if user and verify_password(password, user.hashed_password):
                return user
    except Exception:
        return None


def create_access_token(sub: str) -> str:
    to_encode = {
        "sub": sub,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(to_encode, settings.secret_key, algorithm="HS256")
