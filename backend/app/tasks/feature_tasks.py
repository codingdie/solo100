"""Celery tasks for Feature pipeline execution."""

import asyncio
import logging

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name="app.tasks.feature_tasks.run_feature_pipeline",
    max_retries=3,
    retry_backoff=60,
    retry_backoff_max=600,
    retry_jitter=True,
)
def run_feature_pipeline(self, feature_id: str) -> dict:
    """Entry point Celery task for running a Feature through its pipeline."""
    logger.info("Celery task received for feature_id=%s (attempt=%d)", feature_id, self.request.retries)

    try:
        from app.services.feature_executor import FeatureExecutor

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(FeatureExecutor().run_pipeline(feature_id))
        finally:
            loop.close()

        logger.info("Feature pipeline completed: feature_id=%s, result=%s", feature_id, result)
        return result
    except Exception as exc:
        logger.error("Feature pipeline failed: feature_id=%s, error=%s", feature_id, exc, exc_info=True)
        raise
