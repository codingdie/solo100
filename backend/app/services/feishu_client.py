"""Feishu Incoming Webhook HTTP client.

Failures are logged and silenced — they must never block the calling code.
"""

import logging
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_TIMEOUT: float = 5.0


class FeishuClient:
    """Async client for posting Feishu Incoming Webhook messages."""

    def __init__(self, webhook_url: str | None = None) -> None:
        self._webhook_url = (webhook_url or settings.feishu_webhook_url or "").strip()

    @property
    def is_configured(self) -> bool:
        return bool(self._webhook_url)

    async def post_text(self, text: str) -> bool:
        if not self.is_configured:
            logger.debug("FeishuClient.post_text skipped: webhook URL not configured")
            return False

        payload: dict[str, Any] = {
            "msg_type": "text",
            "content": {"text": text},
        }
        return await self._post(payload)

    async def post_feature_event(
        self,
        feature_id: str,
        event_type: str,
        title: str,
        message: str,
    ) -> bool:
        if not self.is_configured:
            return False

        text = f"[solo100] {title}\n{message}\nFeature: {feature_id}\nEvent: {event_type}"
        payload: dict[str, Any] = {
            "msg_type": "text",
            "content": {"text": text},
        }
        return await self._post(payload)

    async def _post(self, payload: dict[str, Any]) -> bool:
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.post(self._webhook_url, json=payload)
            if resp.status_code == 200:
                return True
            logger.warning("FeishuClient: non-200 response %d", resp.status_code)
            return False
        except Exception as exc:
            logger.warning("FeishuClient: request failed: %s", exc)
            return False
