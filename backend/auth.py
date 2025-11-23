from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from repo.sql_models import User
from patient_manager import SessionLocal
from passlib.context import CryptContext
from datetime import datetime, timedelta, timezone

SECRET_KEY = "stupid_hash_for_now"
ALGO = "HS256"
ACCESS_MIN = 30
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")
pwd = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")



def authenticate(username: str, password: str) -> User | None:
    with SessionLocal() as session:
        user = session.query(User).filter_by(username=username).first()
        if not user:
            return None
        if not pwd.verify(password, user.hashed_password):
            return None
        return user
    

def create_access_token(sub: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_MIN)
    to_encode = {"sub": sub, "exp": expire}
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGO)

async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    print("RAW INCOMING TOKEN:", repr(token))
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGO])
        username: str | None = payload.get("sub")
        if not username:
            raise HTTPException(status_code=401, detail="Invalid token payload")
    except JWTError as e:
        print("JWT DECODE ERROR:", e)
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    with SessionLocal() as session:
        user = session.query(User).filter_by(username=username).first()
        if user is None:
            raise HTTPException(status_code=401, detail="User not found")
        return user
