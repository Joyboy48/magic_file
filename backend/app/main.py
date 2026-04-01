from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import jobs as jobs_router
from app.api import progress as progress_router
from app.api import upload as upload_router
from app.core.config import settings
from app.db.base import Base
from app.db.session import engine


def create_app() -> FastAPI:
    app = FastAPI(title="Async Document Processing")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    # Create tables on startup for this scaffold.
    @app.on_event("startup")
    async def on_startup() -> None:
        Base.metadata.create_all(bind=engine)

    app.include_router(upload_router.router)
    app.include_router(jobs_router.router)
    app.include_router(progress_router.router)

    return app


app = create_app()

