from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from db.connection import db
from .routes import router as courses_router


# ----- Course Info API --------------------
class CourseInfoAPI:
    @staticmethod
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        """Handles API startup and shutdown."""

        await db.init()
        yield


    @staticmethod
    def create() -> FastAPI:
        """Creates and configures the FastAPI app."""

        app = FastAPI(
            title       = "UVic Course Info API",
            description = "API for fetching UVic course and prerequisite data.",
            version     = "1.0.0",
            lifespan    = CourseInfoAPI.lifespan,
        )

        app.add_middleware(
            CORSMiddleware,
            allow_origins = ["*"],
            allow_headers = ["*"],
            allow_methods = ["GET"]
        )

        app.include_router(courses_router, prefix="/course-info-api")

        return app