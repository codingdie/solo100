"""FastAPI router aggregation."""

from app.routers.agents import router as agents_router
from app.routers.approvals import router as approvals_router
from app.routers.features import router as features_router
from app.routers.projects import router as projects_router
from app.routers.websocket import router as websocket_router

__all__ = [
    "projects_router",
    "features_router",
    "approvals_router",
    "agents_router",
    "websocket_router",
]
