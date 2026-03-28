"""Celery tasks package."""

from app.tasks.feature_tasks import run_feature_pipeline

__all__ = ["run_feature_pipeline"]
