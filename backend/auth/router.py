from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.dependencies import get_current_user
from auth.utils import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    create_access_token,
    hash_password,
    verify_password,
)
from database import get_db
from models import User
from schemas import TokenResponse, UserCreate, UserLogin, UserResponse
from core.logger import get_logger

router = APIRouter()
logger = get_logger("auth_router")


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: UserCreate, db: AsyncSession = Depends(get_db)):
    try:
        existing = await db.execute(select(User).where(User.email == payload.email))
        if existing.scalar_one_or_none() is not None:
            logger.warning(
                "Registration failed: Email already registered",
                extra={"structured_data": {"email": payload.email}}
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already registered",
            )

        username_taken = await db.execute(select(User).where(User.username == payload.username))
        if username_taken.scalar_one_or_none() is not None:
            logger.warning(
                "Registration failed: Username already taken",
                extra={"structured_data": {"username": payload.username}}
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Username already taken",
            )

        user = User(
            username=payload.username,
            email=payload.email,
            hashed_password=hash_password(payload.password),
        )
        db.add(user)
        await db.flush()
        await db.refresh(user)
        
        logger.info(
            "User registered successfully",
            extra={"structured_data": {"user_id": user.id, "username": user.username}}
        )
        return user
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Unexpected error during registration",
            exc_info=True,
            extra={"structured_data": {"email": payload.email}}
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected server error occurred during registration. Check logs for details."
        )


@router.post("/login", response_model=TokenResponse)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    try:
        # OAuth2 standard requires 'username' and 'password' form fields.
        # We use the 'username' field to capture the user's email.
        result = await db.execute(select(User).where(User.email == form_data.username))
        user = result.scalar_one_or_none()
        if user is None or not verify_password(form_data.password, user.hashed_password):
            logger.warning(
                "Login failed: Incorrect credentials",
                extra={"structured_data": {"email": form_data.username}}
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        expires_delta = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": str(user.id)},
            expires_delta=expires_delta,
        )
        
        logger.info(
            "User logged in successfully",
            extra={"structured_data": {"user_id": user.id, "username": user.username}}
        )
        
        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            username=user.username,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Unexpected error during login",
            exc_info=True,
            extra={"structured_data": {"email": form_data.username}}
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected server error occurred during login. Check logs for details."
        )


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)):
    return current_user
