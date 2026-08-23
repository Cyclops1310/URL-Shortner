from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from jose import jwt

from app.database import get_db, settings
from app.models.user import User
from app.schemas.auth import (
    RegisterRequest,
    LoginRequest,
    TokenResponse
)


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"]
)


pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto"
)


def hash_password(password: str):
    return pwd_context.hash(password)


def verify_password(
    password: str,
    hashed_password: str
):
    return pwd_context.verify(
        password,
        hashed_password
    )


def create_token(user_id: int):
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )

    payload = {
        "sub": str(user_id),
        "exp": expire
    }

    return jwt.encode(
        payload,
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM
    )


@router.post("/register")
def register(
    request: RegisterRequest,
    db: Session = Depends(get_db)
):
    existing_user = db.query(User).filter(
        User.email == request.email
    ).first()

    if existing_user:
        raise HTTPException(
            status_code=409,
            detail="Email already registered"
        )

    user = User(
        email=request.email,
        password_hash=hash_password(request.password)
    )

    db.add(user)
    db.commit()

    return {
        "message": "User registered successfully"
    }


@router.post(
    "/login",
    response_model=TokenResponse
)
def login(
    request: LoginRequest,
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(
        User.email == request.email
    ).first()

    if not user or not verify_password(
        request.password,
        user.password_hash
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
        )

    token = create_token(user.id)

    return {
        "access_token": token,
        "token_type": "bearer"
    }