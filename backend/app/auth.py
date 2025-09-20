import os
from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session
from .database import get_db
from .models import User


JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-change-me")
JWT_ALG = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
COOKIE_NAME = os.getenv("AUTH_COOKIE_NAME", "access_token")
COOKIE_DOMAIN = os.getenv("AUTH_COOKIE_DOMAIN", None)


pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
	return pwd.hash(password)


def verify_password(password: str, hashed: str) -> bool:
	return pwd.verify(password, hashed)


def create_access_token(sub: str, extra: dict | None = None, expires_minutes: int | None = None) -> str:
	to_encode = {"sub": sub}
	if extra:
		to_encode.update(extra)
	expire = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes or ACCESS_TOKEN_EXPIRE_MINUTES)
	to_encode.update({"exp": expire})
	return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALG)


def set_auth_cookie(response, token: str):
	response.set_cookie(
		key=COOKIE_NAME,
		value=token,
		httponly=True,
		secure=False, # set True behind HTTPS in prod
		samesite="lax",
		domain=COOKIE_DOMAIN,
		path="/",
		max_age=60*60*24,
	)


def clear_auth_cookie(response):
	response.delete_cookie(COOKIE_NAME, domain=COOKIE_DOMAIN, path="/")


async def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
	token = request.cookies.get(COOKIE_NAME)
	if not token:
		raise HTTPException(status_code=401, detail="Not authenticated")
	try:
		payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
		sub: str = payload.get("sub")
		if not sub:
			raise HTTPException(status_code=401, detail="Invalid token")
	except JWTError as e:
		raise HTTPException(status_code=401, detail="Invalid token")
	user = db.query(User).filter(User.username == sub).first()
	if not user:
		raise HTTPException(status_code=401, detail="User not found")
	return user