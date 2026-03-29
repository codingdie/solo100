"""Notification Hub — single source for all push notifications.

v0.1: WebSocket + Feishu channels.
"""

import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class FeatureEventType(str, Enum):
    STATUS_CHANGED = "status_change"
    LOG = "log"
    STAGE_COMPLETED = "stage_complete"
    APPROVAL_REQUIRED = "awaiting_approval"
    ERROR = "error"


@dataclass
class FeatureEvent:
    type: FeatureEventType
    feature_id: str
    stage: str | None = None
    message: str | None = None
    data: dict[str, Any] | None = None
    timestamp: str | None = None

    def __post_init__(self) -> None:
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc).isoformat()


class NotificationChannel:
    """Abstract notification channel interface."""

    async def send(self, feature_id: str, payload: dict[str, Any]) -> None:
        raise NotImplementedError


class WebSocketChannel(NotificationChannel):
    """Push notifications over FastAPI WebSocket to connected browser clients."""

    async def send(self, feature_id: str, payload: dict[str, Any]) -> None:
        from app.routers.websocket import push_feature_event
        await push_feature_event(feature_id, payload)


class FeishuChannel(NotificationChannel):
    """Push important status-change events to Feishu Webhook.

    Only STATUS_CHANGED, APPROVAL_REQUIRED, and ERROR events are forwarded —
    LOG events are too noisy for Feishu.
    """

    _IMPORTANT_TYPES = {
        FeatureEventType.STATUS_CHANGED.value,
        FeatureEventType.APPROVAL_REQUIRED.value,
        FeatureEventType.ERROR.value,
    }

    def __init__(self) -> None:
        from app.services.feishu_client import FeishuClient
        self._client = FeishuClient()

    async def send(self, feature_id: str, payload: dict[str, Any]) -> None:
        if payload.get("type") not in self._IMPORTANT_TYPES:
            return
        if not self._client.is_configured:
            return

        event_type = payload.get("type", "")
        message = payload.get("message", "")
        title = {
            FeatureEventType.STATUS_CHANGED.value: "🔄 Feature Status Changed",
            FeatureEventType.APPROVAL_REQUIRED.value: "⏳ Approval Required",
            FeatureEventType.ERROR.value: "❌ Feature Error",
        }.get(event_type, "solo100 Notification")

        await self._client.post_feature_event(
            feature_id=feature_id,
            event_type=event_type,
            title=title,
            message=message or "",
        )


class NotificationHub:
    """Unified push notification hub."""

    def __init__(self) -> None:
        self._channels: list[NotificationChannel] = []

    def register_channel(self, channel: NotificationChannel) -> None:
        self._channels.append(channel)

    async def emit(self, event: FeatureEvent) -> None:
        payload = asdict(event)
        for channel in self._channels:
            try:
                await channel.send(event.feature_id, payload)
            except Exception as exc:
                logger.error(
                    "NotificationHub: channel %s failed for feature %s: %s",
                    type(channel).__name__, event.feature_id, exc,
                )


# Module-level singleton
hub = NotificationHub()
hub.register_channel(WebSocketChannel())
hub.register_channel(FeishuChannel())


async def notify_status_changed(
    feature_id: str, old_status: str, new_status: str, stage: str | None = None
) -> None:
    await hub.emit(FeatureEvent(
        type=FeatureEventType.STATUS_CHANGED, feature_id=feature_id, stage=stage,
        message=f"Status changed: {old_status} → {new_status}",
        data={"old_status": old_status, "new_status": new_status},
    ))


async def notify_awaiting_approval(feature_id: str, stage: str, message: str) -> None:
    await hub.emit(FeatureEvent(
        type=FeatureEventType.APPROVAL_REQUIRED, feature_id=feature_id,
        stage=stage, message=message,
    ))


async def notify_stage_completed(
    feature_id: str, stage: str, result_data: dict[str, Any] | None = None
) -> None:
    await hub.emit(FeatureEvent(
        type=FeatureEventType.STAGE_COMPLETED, feature_id=feature_id,
        stage=stage, data=result_data,
    ))


async def notify_error(feature_id: str, stage: str, message: str) -> None:
    await hub.emit(FeatureEvent(
        type=FeatureEventType.ERROR, feature_id=feature_id,
        stage=stage, message=message,
    ))


async def notify_log(feature_id: str, stage: str, line: str) -> None:
    await hub.emit(FeatureEvent(
        type=FeatureEventType.LOG, feature_id=feature_id,
        stage=stage, message=line,
    ))
