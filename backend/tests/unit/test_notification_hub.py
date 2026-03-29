"""Unit tests for NotificationHub and FeishuChannel."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.notification_hub import (
    FeatureEvent,
    FeatureEventType,
    FeishuChannel,
    NotificationChannel,
    NotificationHub,
    WebSocketChannel,
)


class TestNotificationHub:
    @pytest.mark.asyncio
    async def test_emit_calls_all_channels(self) -> None:
        hub = NotificationHub()
        ch1 = MagicMock(spec=NotificationChannel)
        ch1.send = AsyncMock()
        ch2 = MagicMock(spec=NotificationChannel)
        ch2.send = AsyncMock()
        hub.register_channel(ch1)
        hub.register_channel(ch2)

        event = FeatureEvent(
            type=FeatureEventType.STATUS_CHANGED,
            feature_id="feat-001",
            message="pending → brainstorming",
        )
        await hub.emit(event)

        ch1.send.assert_awaited_once()
        ch2.send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_channel_failure_does_not_propagate(self) -> None:
        hub = NotificationHub()
        bad_ch = MagicMock(spec=NotificationChannel)
        bad_ch.send = AsyncMock(side_effect=RuntimeError("boom"))
        hub.register_channel(bad_ch)

        event = FeatureEvent(
            type=FeatureEventType.ERROR,
            feature_id="feat-001",
            message="something failed",
        )
        # Should not raise
        await hub.emit(event)

    @pytest.mark.asyncio
    async def test_emit_passes_correct_payload(self) -> None:
        hub = NotificationHub()
        received: list[dict] = []

        class CapturingChannel(NotificationChannel):
            async def send(self, feature_id, payload):
                received.append(payload)

        hub.register_channel(CapturingChannel())

        event = FeatureEvent(
            type=FeatureEventType.APPROVAL_REQUIRED,
            feature_id="feat-abc",
            stage="brainstorming",
            message="Waiting for approval",
        )
        await hub.emit(event)

        assert len(received) == 1
        assert received[0]["type"] == "awaiting_approval"
        assert received[0]["feature_id"] == "feat-abc"
        assert received[0]["stage"] == "brainstorming"


class TestFeishuChannel:
    @pytest.mark.asyncio
    async def test_forwards_status_change_events(self) -> None:
        channel = FeishuChannel()
        channel._client = MagicMock()
        channel._client.is_configured = True
        channel._client.post_feature_event = AsyncMock(return_value=True)

        await channel.send("feat-001", {
            "type": "status_change",
            "feature_id": "feat-001",
            "message": "pending → brainstorming",
        })

        channel._client.post_feature_event.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_skips_log_events(self) -> None:
        channel = FeishuChannel()
        channel._client = MagicMock()
        channel._client.is_configured = True
        channel._client.post_feature_event = AsyncMock(return_value=True)

        await channel.send("feat-001", {
            "type": "log",
            "feature_id": "feat-001",
            "message": "some log line",
        })

        channel._client.post_feature_event.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_skips_when_not_configured(self) -> None:
        channel = FeishuChannel()
        channel._client = MagicMock()
        channel._client.is_configured = False
        channel._client.post_feature_event = AsyncMock(return_value=True)

        await channel.send("feat-001", {
            "type": "status_change",
            "message": "test",
        })

        channel._client.post_feature_event.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_forwards_error_events(self) -> None:
        channel = FeishuChannel()
        channel._client = MagicMock()
        channel._client.is_configured = True
        channel._client.post_feature_event = AsyncMock(return_value=True)

        await channel.send("feat-001", {
            "type": "error",
            "feature_id": "feat-001",
            "message": "Pipeline failed",
        })

        channel._client.post_feature_event.assert_awaited_once()
        call_kwargs = channel._client.post_feature_event.call_args.kwargs
        assert "❌" in call_kwargs["title"]

    @pytest.mark.asyncio
    async def test_forwards_approval_required_events(self) -> None:
        channel = FeishuChannel()
        channel._client = MagicMock()
        channel._client.is_configured = True
        channel._client.post_feature_event = AsyncMock(return_value=True)

        await channel.send("feat-001", {
            "type": "awaiting_approval",
            "feature_id": "feat-001",
            "message": "Waiting for human approval",
        })

        channel._client.post_feature_event.assert_awaited_once()
        call_kwargs = channel._client.post_feature_event.call_args.kwargs
        assert "⏳" in call_kwargs["title"]
