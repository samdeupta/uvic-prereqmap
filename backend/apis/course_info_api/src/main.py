from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI

from db.connection import db
from routes import router as courses_router


# ----- API Lifespan Handler --------------------
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Handles API startup and shutdown."""

    await db.init()
    yield


# ----- FastAPI App --------------------
app = FastAPI(
    title       = "UVic Course Info API",
    description = "API for fetching UVic course and prerequisite data.",
    version     = "1.0.0",
    lifespan    = lifespan,
)


# ----- API Router --------------------
app.include_router(courses_router, prefix="/course-info-api")