"""FastAPI application entry point."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import engine
from app.routers import (
    agents_router,
    approvals_router,
    features_router,
    projects_router,
    websocket_router,
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup: create all DB tables via managed schema."""
    from app.database import Base
    from app.models import (
        AgentConfig,
        Feature,
        FeatureExecution,
        Project,
        ReviewReport,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(
    title="solo100 API",
    description="AI-powered Feature development workflow engine.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(projects_router)
app.include_router(features_router)
app.include_router(approvals_router)
app.include_router(agents_router)
app.include_router(websocket_router)


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Liveness probe endpoint."""
    return {"status": "ok"}


@app.get("/")
async def root() -> dict[str, str]:
    """Root redirect to API docs."""
    return {"message": "solo100 API is running. See /docs for Swagger UI."}
