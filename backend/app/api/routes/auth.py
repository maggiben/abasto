from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_current_user_optional
from app.core.security import create_access_token, hash_password, verify_password
from app.db.session import get_session
from app.models.user import User
from app.schemas.user import Token, UserCreate, UserLogin, UserPublic

router = APIRouter()


@router.post("/register", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
async def register(
    body: UserCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    actor: Annotated[User | None, Depends(get_current_user_optional)],
) -> User:
    if body.is_staff and (actor is None or not actor.is_staff):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only staff can create staff users",
        )
    result = await session.execute(select(User).where(User.email == body.email))
    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )
    user = User(
        email=body.email,
        hashed_password=hash_password(body.password),
        is_staff=body.is_staff,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


@router.post("/login", response_model=Token)
async def login(
    body: UserLogin,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Token:
    result = await session.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )
    access_token = create_access_token(email=user.email, user_id=user.id)
    return Token(access_token=access_token)


@router.get("/me", response_model=UserPublic)
async def read_me(current_user: Annotated[User, Depends(get_current_user)]) -> User:
    return current_user
