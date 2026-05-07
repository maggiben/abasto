from contextlib import asynccontextmanager
import logging

import app.models  # noqa: F401 — register ORM mappers
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.api.router import api_router
from app.config import get_settings
from app.core.security import hash_password
from app.db.session import AsyncSessionLocal, engine
from app.models.user import User

logger = logging.getLogger(__name__)


async def ensure_bootstrap_admin_user() -> None:
    settings = get_settings()
    email = settings.bootstrap_admin_email
    password = settings.bootstrap_admin_password
    if not email or not password:
        return

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if user is None:
            session.add(
                User(
                    email=email,
                    hashed_password=hash_password(password),
                    is_active=True,
                    is_staff=True,
                )
            )
            await session.commit()
            logger.info("Created bootstrap admin user: %s", email)
            return
        if not user.is_staff or not user.is_active:
            user.is_staff = True
            user.is_active = True
            await session.commit()
            logger.info("Ensured bootstrap admin privileges for user: %s", email)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await ensure_bootstrap_admin_user()
    yield
    await engine.dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_origin_regex=settings.cors_origin_regex,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router)
    return app


app = create_app()
