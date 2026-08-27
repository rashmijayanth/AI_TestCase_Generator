"""FastAPI application factory."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from testgen.api.routers import audit, auth, documents, projects, requirements, traceability
from testgen.platform.config import get_settings
from testgen.platform.logging import configure_logging
from testgen.platform.tracing import configure_tracing


@asynccontextmanager
async def _lifespan(_app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings)
    configure_tracing(settings)
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Automatic Test Case Generation AI",
        version="0.1.0",
        lifespan=_lifespan,
    )

    @app.get("/health", tags=["health"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(auth.router)
    app.include_router(projects.router)
    app.include_router(documents.router)
    app.include_router(requirements.router)
    app.include_router(traceability.router)
    app.include_router(audit.router)
    return app


app = create_app()
