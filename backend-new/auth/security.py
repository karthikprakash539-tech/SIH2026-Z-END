"""
BlockSync authentication & RBAC.

Place at: backend/auth/security.py

Provides:
  - password hashing (no external service needed, uses hashlib+salt)
  - JWT creation/verification
  - a FastAPI dependency (get_current_user) that reads the token from
    the Authorization header and returns the logged-in user's row
  - a require_role() dependency factory for role-gated endpoints
"""

import hashlib
import os
import sys
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy.orm import sessionmaker

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "models"))
from models import engine, User

SECRET_KEY = "blocksync-hackathon-demo-secret-change-in-real-deployment"  # fine for a prototype
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 120

Session = sessionmaker(bind=engine)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def hash_password(password: str) -> str:
    salt = "blocksync_salt"  # fine for a prototype; use per-user salts in real deployment
    return hashlib.sha256((salt + password).encode()).hexdigest()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return hash_password(plain_password) == hashed_password


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    db = Session()
    user = db.query(User).filter(User.username == username).first()
    db.close()
    if user is None:
        raise credentials_exception
    return user


def require_role(*allowed_roles):
    """Usage: Depends(require_role('admin', 'engineering_officer'))"""
    def role_checker(current_user=Depends(get_current_user)):
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{current_user.role}' is not permitted to perform this action.",
            )
        return current_user
    return role_checker