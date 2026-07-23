from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import uvicorn

from shiloh.config import Settings, get_settings
from shiloh.routes import admin, assignments, auth, flashcards, profile
from shiloh.services import AIService, GridFSStorage, PDFProcessingService


def create_app(
    *,
    settings: Settings | None = None,
    database: Any | None = None,
    ai_service: AIService | None = None,
    file_storage: GridFSStorage | Any | None = None,
    pdf_service: PDFProcessingService | Any | None = None,
) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.settings = settings
        app.state.ai_service = ai_service or AIService(settings)
        app.state.pdf_service = pdf_service or PDFProcessingService(
            ocr_languages=settings.ocr_languages
        )
        app.state.mongo_client = None
        if database is not None:
            app.state.db = database
            app.state.file_storage = file_storage
        else:
            client = AsyncIOMotorClient(settings.mongo_url)
            app.state.mongo_client = client
            app.state.db = client[settings.mongo_db_name]
            app.state.file_storage = file_storage or GridFSStorage(app.state.db)
        yield
        if app.state.mongo_client is not None:
            app.state.mongo_client.close()

    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    async def healthcheck() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ready")
    async def readiness_check(request: Request) -> dict[str, str]:
        try:
            await request.app.state.db.command("ping")
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database is not ready.",
            ) from exc
        return {"status": "ready"}

    app.include_router(auth.router)
    app.include_router(profile.router)
    app.include_router(flashcards.router)
    app.include_router(assignments.router)
    app.include_router(admin.router)
    return app


app = create_app()


def run() -> None:
    uvicorn.run("shiloh.main:app", host="0.0.0.0", port=8000, reload=False)
