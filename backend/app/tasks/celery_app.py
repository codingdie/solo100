"""Celery application instance and configuration."""

from celery import Celery

from app.config import settings

celery_app = Celery(
    "solo100",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.tasks.feature_tasks"],
)

celery_app.conf.task_serializer = "json"
celery_app.conf.result_serializer = "json"
celery_app.conf.accept_content = ["json"]
celery_app.conf.result_expires = 86400
celery_app.conf.task_default_queue = "solo100_features"
celery_app.conf.beat_schedule = {}
