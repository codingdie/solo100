I now have all the context needed. Let me output the complete plan document.

---

# solo100 通知层实现计划

**文档路径**: `docs/superpowers/plans/2026-03-26-plan-4-notification-layer.md`
**版本**: v0.1 Notification Layer
**日期**: 2026-03-26
**前置依赖**: plan-1 (backend-foundation) 必须先完成

---

## Goal

实现 solo100 通知层（Notification Hub），统一推送 Feature 状态变更和 Agent 日志流到两个渠道：浏览器 WebSocket 和飞书 Webhook。NotificationHub 作为唯一入口，供 FeatureExecutor、ApprovalGateway 等业务层调用，业务逻辑完全与推送渠道解耦。

---

## Architecture

```
app/services/
  ├── notification_hub.py   # 通知总入口，分发到各渠道
  └── feishu_client.py       # 飞书 Webhook HTTP 客户端

app/routers/
  └── websocket.py           # 已存在，含 push_feature_event 函数

业务层调用链：
  FeatureExecutor / ApprovalGateway
        │
        ▼
  NotificationHub.notify(event)
        │
        ├── push_feature_event()  ──→ 浏览器 WebSocket
        │                                   (_active_connections[feature_id])
        │
        └── FeishuClient.post()       ──→ 飞书 Webhook
                                            (FEISHU_WEBHOOK_URL)
```

**设计原则**：
- NotificationHub 是薄封装，复用 `websocket.py` 中已有的 `push_feature_event` 函数
- 飞书 Webhook 失败时静默记录日志，不阻塞主流程
- 所有事件格式由 NotificationHub 内部格式化，业务层只传原始数据 dict

---

## Tech Stack

| 组件 | 技术 |
|------|------|
| HTTP Client | httpx 0.26.0 (async, timeout=5s) |
| Logging | Python stdlib `logging` |
| DateTime | datetime.utcnow().isoformat() |
| Testing | pytest, pytest-asyncio, respx (mock HTTP) |
| WebSocket | FastAPI WebSocket (已有) |

---

## 前置依赖检查

在开始之前，确认以下文件已存在（plan-1 产出物）：

```
backend/app/config.py          # 含 feishu_webhook_url 配置
backend/app/routers/websocket.py  # 含 push_feature_event 函数
backend/requirements.txt       # 含 httpx 依赖
```

如果这些文件不存在，先执行 plan-1。

---

## Task 1: 飞书 Webhook HTTP 客户端

**Files**
- 创建: `backend/app/services/__init__.py`
- 创建: `backend/app/services/feishu_client.py`
- 创建: `backend/tests/unit/test_feishu_client.py`

### 步骤 1.1 创建 `backend/app/services/__init__.py`

```python
"""Business logic services."""

from app.services.feishu_client import FeishuClient
from app.services.notification_hub import NotificationHub

__all__ = ["FeishuClient", "NotificationHub"]
```

### 步骤 1.2 创建 `backend/app/services/feishu_client.py`

```python
"""Feishu Incoming Webhook HTTP client.

Sends one-way notification messages to a configured Feishu Incoming Webhook URL.
Failures are logged and silenced — they must never block the calling code.
"""

import logging
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# Feishu Incoming Webhook API base
_FEISHU_API = "https://open.feishu.cn/open-apis/bot/v2/hook"

# 5-second timeout for all HTTP requests
_TIMEOUT: float = 5.0


class FeishuClient:
    """Async client for posting Feishu Incoming Webhook messages."""

    def __init__(self, webhook_url: str | None = None) -> None:
        """
        Args:
            webhook_url: Feishu Incoming Webhook URL. Falls back to settings.feishu_webhook_url.
        """
        self._webhook_url = (webhook_url or settings.feishu_webhook_url or "").strip()

    @property
    def is_configured(self) -> bool:
        """Return True only if a non-empty webhook URL is available."""
        return bool(self._webhook_url)

    async def post_text(self, text: str) -> bool:
        """
        Send a plain-text message to the Feishu webhook.

        Args:
            text: Message content (Feishu renders newlines \\n as line breaks).

        Returns:
            True if the request succeeded (2xx); False otherwise.
        """
        if not self.is_configured:
            logger.debug("FeishuClient.post_text skipped: webhook URL not configured")
            return False

        payload: dict[str, Any] = {
            "msg_type": "text",
            "content": {"text": text},
        }

        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                response = await client.post(self._webhook_url, json=payload)
                if response.is_success:
                    logger.info("Feishu webhook posted successfully: %s", text[:80])
                    return True
                else:
                    logger.warning(
                        "Feishu webhook returned %s: %s",
                        response.status_code,
                        response.text[:200],
                    )
                    return False
        except httpx.TimeoutException:
            logger.warning("Feishu webhook timed out after %.1fs", _TIMEOUT)
            return False
        except httpx.RequestError as exc:
            logger.error("Feishu webhook request failed: %s", exc)
            return False


# Shared singleton instance — reused across the app
feishu_client = FeishuClient()
```

### 步骤 1.3 创建 `backend/tests/unit/test_feishu_client.py`

```python
"""Unit tests for FeishuClient."""

import pytest
from unittest.mock import AsyncMock, patch

from app.services.feishu_client import FeishuClient


class TestFeishuClientIsConfigured:
    """Tests for FeishuClient.is_configured property."""

    def test_is_configured_false_when_empty(self) -> None:
        """When webhook_url is empty string, is_configured returns False."""
        client = FeishuClient(webhook_url="")
        assert client.is_configured is False

    def test_is_configured_false_when_none(self) -> None:
        """When webhook_url is None, falls back to settings (also empty)."""
        with patch("app.services.feishu_client.settings") as mock_settings:
            mock_settings.feishu_webhook_url = ""
            client = FeishuClient()
            assert client.is_configured is False

    def test_is_configured_true_when_valid_url(self) -> None:
        """A non-empty webhook URL makes is_configured return True."""
        client = FeishuClient(webhook_url="https://open.feishu.cn/open-apis/bot/v2/hook/abc123")
        assert client.is_configured is True

    def test_is_configured_strips_whitespace(self) -> None:
        """A URL with only whitespace is treated as not configured."""
        client = FeishuClient(webhook_url="   ")
        assert client.is_configured is False


class TestFeishuClientPostText:
    """Tests for FeishuClient.post_text()."""

    @pytest.mark.asyncio
    async def test_post_text_returns_false_when_not_configured(self) -> None:
        """If no webhook URL is set, post_text returns False and makes no HTTP call."""
        client = FeishuClient(webhook_url="")
        result = await client.post_text("hello")
        assert result is False

    @pytest.mark.asyncio
    async def test_post_text_returns_true_on_200(self) -> None:
        """On HTTP 200, post_text returns True."""
        client = FeishuClient(webhook_url="https://open.feishu.cn/open-apis/bot/v2/hook/abc123")
        mock_response = AsyncMock()
        mock_response.is_success = True
        mock_response.status_code = 200
        mock_response.text = "ok"

        with patch("httpx.AsyncClient") as MockAsyncClient:
            mock_client_instance = AsyncMock()
            mock_client_instance.post = AsyncMock(return_value=mock_response)
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            MockAsyncClient.return_value = mock_client_instance

            result = await client.post_text("[solo100] Feature test")

        assert result is True
        mock_client_instance.post.assert_called_once()
        call_kwargs = mock_client_instance.post.call_args
        assert call_kwargs.kwargs["json"] == {
            "msg_type": "text",
            "content": {"text": "[solo100] Feature test"},
        }

    @pytest.mark.asyncio
    async def test_post_text_returns_false_on_400(self) -> None:
        """On HTTP 400/4xx, post_text returns False."""
        client = FeishuClient(webhook_url="https://open.feishu.cn/open-apis/bot/v2/hook/abc123")
        mock_response = AsyncMock()
        mock_response.is_success = False
        mock_response.status_code = 400
        mock_response.text = "invalid payload"

        with patch("httpx.AsyncClient") as MockAsyncClient:
            mock_client_instance = AsyncMock()
            mock_client_instance.post = AsyncMock(return_value=mock_response)
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            MockAsyncClient.return_value = mock_client_instance

            result = await client.post_text("hello")

        assert result is False

    @pytest.mark.asyncio
    async def test_post_text_returns_false_on_timeout(self) -> None:
        """On httpx.TimeoutException, post_text returns False (no exception raised)."""
        import httpx

        client = FeishuClient(webhook_url="https://open.feishu.cn/open-apis/bot/v2/hook/abc123")

        with patch("httpx.AsyncClient") as MockAsyncClient:
            mock_client_instance = AsyncMock()
            mock_client_instance.post = AsyncMock(side_effect=httpx.TimeoutException("timed out"))
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            MockAsyncClient.return_value = mock_client_instance

            result = await client.post_text("hello")

        assert result is False

    @pytest.mark.asyncio
    async def test_post_text_returns_false_on_network_error(self) -> None:
        """On httpx.RequestError, post_text returns False (no exception raised)."""
        import httpx

        client = FeishuClient(webhook_url="https://open.feishu.cn/open-apis/bot/v2/hook/abc123")

        with patch("httpx.AsyncClient") as MockAsyncClient:
            mock_client_instance = AsyncMock()
            mock_client_instance.post = AsyncMock(side_effect=httpx.RequestError("connection refused"))
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            MockAsyncClient.return_value = mock_client_instance

            result = await client.post_text("hello")

        assert result is False

    @pytest.mark.asyncio
    async def test_post_text_includes_solo100_prefix_in_payload(self) -> None:
        """The caller is responsible for including [solo100] in the text; we send exactly what is passed."""
        client = FeishuClient(webhook_url="https://open.feishu.cn/open-apis/bot/v2/hook/abc123")
        mock_response = AsyncMock()
        mock_response.is_success = True
        mock_response.status_code = 200
        mock_response.text = "ok"

        with patch("httpx.AsyncClient") as MockAsyncClient:
            mock_client_instance = AsyncMock()
            mock_client_instance.post = AsyncMock(return_value=mock_response)
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            MockAsyncClient.return_value = mock_client_instance

            await client.post_text("[solo100] Feature「Login」status变更：pending → brainstorming")

        call_kwargs = mock_client_instance.post.call_args
        assert "[solo100]" in call_kwargs.kwargs["json"]["content"]["text"]
```

**Commit:**

```bash
git add backend/app/services/__init__.py \
         backend/app/services/feishu_client.py \
         backend/tests/unit/test_feishu_client.py
git commit -m "feat: add FeishuClient with silent failure and 5s timeout

添加 app/services/feishu_client.py：异步 HTTP 客户端，POST 纯文本消息到飞书
Incoming Webhook，超时 5 秒，失败时静默记录 WARNING 日志而非抛异常。
添加对应单元测试，覆盖 configured 状态、所有错误路径（400/timeout/network error）
"
```

---

## Task 2: NotificationHub 服务实现

**Files**
- 修改: `backend/app/services/__init__.py`
- 创建: `backend/app/services/notification_hub.py`
- 创建: `backend/tests/unit/test_notification_hub.py`

### 步骤 2.1 更新 `backend/app/services/__init__.py`

在文件末尾添加导出：

```python
"""Business logic services."""

from app.services.feishu_client import FeishuClient
from app.services.notification_hub import NotificationHub

__all__ = ["FeishuClient", "NotificationHub"]
```

### 步骤 2.2 创建 `backend/app/services/notification_hub.py`

```python
"""NotificationHub — unified event dispatcher for Feature state changes and log streams.

Publishes to two channels:
  1. WebSocket  — via the existing push_feature_event() in app.routers.websocket
  2. Feishu     — via FeishuClient (one-way webhook, silent on failure)

Business-layer callers (FeatureExecutor, ApprovalGateway, etc.) should always call
NotificationHub rather than pushing directly to channels, so that:
  - All events are formatted consistently
  - Channels can be added/removed without touching callers
  - Feishu is never a hard dependency (failures do not propagate)
"""

import logging
from datetime import datetime
from typing import Any

from app.routers.websocket import push_feature_event as _ws_push
from app.services.feishu_client import feishu_client

logger = logging.getLogger(__name__)

# All event types emitted by the system
FEATURE_EVENT_TYPES = frozenset([
    "status_change",
    "log",
    "stage_complete",
    "awaiting_approval",
    "error",
])


class NotificationHub:
    """
    Unified notification dispatcher.

    Instantiate once per app startup and reuse. All methods are async.
    """

    def __init__(
        self,
        feishu_webhook_url: str | None = None,
        include_feishu: bool = True,
    ) -> None:
        """
        Args:
            feishu_webhook_url: Override the Feishu webhook URL (defaults to settings).
            include_feishu: Set to False to disable Feishu notifications entirely.
        """
        self._feishu = feishu_client
        if feishu_webhook_url:
            # Build a client with an explicit URL override for this instance
            from app.services.feishu_client import FeishuClient
            self._feishu = FeishuClient(webhook_url=feishu_webhook_url)
        self._include_feishu = include_feishu

    # -------------------------------------------------------------------------
    # Public notification methods
    # -------------------------------------------------------------------------

    async def notify_status_change(
        self,
        feature_id: str,
        old_status: str,
        new_status: str,
        feature_title: str = "",
    ) -> None:
        """
        Broadcast a Feature status transition to all channels.

        Args:
            feature_id: UUID of the Feature.
            old_status: Previous status string.
            new_status: New status string.
            feature_title: Optional title for human-readable Feishu messages.
        """
        event: dict[str, Any] = {
            "type": "status_change",
            "feature_id": feature_id,
            "old_status": old_status,
            "new_status": new_status,
        }
        await self._broadcast(feature_id, event)

        if self._include_feishu and feature_title:
            text = self._format_feishu_status_change(
                feature_title=feature_title,
                old_status=old_status,
                new_status=new_status,
            )
            await self._feishu.post_text(text)

    async def notify_log(
        self,
        feature_id: str,
        stage: str,
        line: str,
    ) -> None:
        """
        Stream a single log line to the WebSocket.

        Note: Feishu does NOT receive log events (too high frequency).
        """
        event: dict[str, Any] = {
            "type": "log",
            "feature_id": feature_id,
            "stage": stage,
            "line": line,
        }
        # WebSocket only — no Feishu
        await _ws_push(feature_id, event)

    async def notify_stage_complete(
        self,
        feature_id: str,
        stage: str,
        result: dict[str, Any],
    ) -> None:
        """
        Notify that a FeatureExecution stage has finished.

        Note: Feishu does NOT receive stage_complete (Feishu only mirrors
        user-facing status transitions).
        """
        event: dict[str, Any] = {
            "type": "stage_complete",
            "feature_id": feature_id,
            "stage": stage,
            "result": result,
        }
        # WebSocket only
        await _ws_push(feature_id, event)

    async def notify_awaiting_approval(
        self,
        feature_id: str,
        stage: str,
        message: str,
    ) -> None:
        """
        Notify the UI that the Feature is waiting for human intervention.

        Feishu receives a brief notice so the user knows action is required.
        """
        event: dict[str, Any] = {
            "type": "awaiting_approval",
            "feature_id": feature_id,
            "stage": stage,
            "message": message,
        }
        await self._broadcast(feature_id, event)

        if self._include_feishu:
            text = (
                f"[solo100] Feature 等待人工确认：{stage}\n"
                f"请访问 Web UI 处理：{message}"
            )
            await self._feishu.post_text(text)

    async def notify_error(
        self,
        feature_id: str,
        stage: str,
        message: str,
    ) -> None:
        """
        Notify the UI of a runtime error in a stage.

        Feishu receives an error alert so the user is notified immediately.
        """
        event: dict[str, Any] = {
            "type": "error",
            "feature_id": feature_id,
            "stage": stage,
            "message": message,
        }
        await self._broadcast(feature_id, event)

        if self._include_feishu:
            text = (
                f"[solo100] Feature 执行出错：{stage}\n"
                f"错误信息：{message}"
            )
            await self._feishu.post_text(text)

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------

    async def _broadcast(self, feature_id: str, event: dict[str, Any]) -> None:
        """
        Push an event to the WebSocket channel.

        Feishu is NOT included here — callers that also want Feishu do so explicitly.
        """
        await _ws_push(feature_id, event)

    @staticmethod
    def _format_feishu_status_change(
        feature_title: str,
        old_status: str,
        new_status: str,
    ) -> str:
        """
        Format a Feishu plain-text status-change message.

        Format: "[solo100] Feature「{title}」状态变更：{old} → {new}"
        """
        return (
            f"[solo100] Feature「{feature_title}」状态变更："
            f"{old_status} → {new_status}"
        )


# Shared singleton instance — used by FeatureExecutor and ApprovalGateway
notification_hub = NotificationHub()
```

### 步骤 2.3 创建 `backend/tests/unit/test_notification_hub.py`

```python
"""Unit tests for NotificationHub.

Tests cover:
  - Event type dispatched to WebSocket
  - Feishu post_text called (or not) for each event type
  - Feishu failures do not raise exceptions
  - Feishu silenced when include_feishu=False or not configured
"""

import pytest
from unittest.mock import AsyncMock, patch

from app.services.notification_hub import NotificationHub


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class FakeWsPush:
    """Records every call to push_feature_event for assertion."""

    calls: list[dict] = []

    @classmethod
    def reset(cls) -> None:
        cls.calls.clear()

    @classmethod
    async def fake_push(cls, feature_id: str, event: dict) -> None:
        cls.calls.append({"feature_id": feature_id, "event": event})


class FakeFeishuClient:
    """Fake that tracks post_text calls."""

    post_text_calls: list[str] = []
    should_fail: bool = False

    @classmethod
    def reset(cls) -> None:
        cls.post_text_calls.clear()
        cls.should_fail = False

    @classmethod
    async def post_text(cls, text: str) -> bool:
        cls.post_text_calls.append(text)
        return not cls.should_fail


# ---------------------------------------------------------------------------
# notify_status_change
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_notify_status_change_pushes_ws_event() -> None:
    """notify_status_change calls WebSocket push with correct event shape."""
    FakeWsPush.reset()
    FakeFeishuClient.reset()

    hub = NotificationHub(include_feishu=False)
    with patch("app.services.notification_hub._ws_push", side_effect=FakeWsPush.fake_push):
        await hub.notify_status_change(
            feature_id="feat-123",
            old_status="pending",
            new_status="brainstorming",
        )

    assert len(FakeWsPush.calls) == 1
    call = FakeWsPush.calls[0]
    assert call["feature_id"] == "feat-123"
    assert call["event"]["type"] == "status_change"
    assert call["event"]["old_status"] == "pending"
    assert call["event"]["new_status"] == "brainstorming"
    assert "timestamp" in call["event"]


@pytest.mark.asyncio
async def test_notify_status_change_posts_feishu_when_title_provided() -> None:
    """Feishu is called when feature_title is non-empty."""
    FakeWsPush.reset()
    FakeFeishuClient.reset()

    hub = NotificationHub(include_feishu=True)
    fake_feishu = FakeFeishuClient()
    with patch("app.services.notification_hub._ws_push", side_effect=FakeWsPush.fake_push), \
         patch.object(hub, "_feishu", fake_feishu):
        await hub.notify_status_change(
            feature_id="feat-123",
            old_status="pending",
            new_status="brainstorming",
            feature_title="Add dark mode",
        )

    assert len(fake_feishu.post_text_calls) == 1
    text = fake_feishu.post_text_calls[0]
    assert "[solo100]" in text
    assert "Add dark mode" in text
    assert "pending" in text
    assert "brainstorming" in text


@pytest.mark.asyncio
async def test_notify_status_change_skips_feishu_when_no_title() -> None:
    """Feishu is NOT called if feature_title is empty."""
    FakeWsPush.reset()
    FakeFeishuClient.reset()

    hub = NotificationHub(include_feishu=True)
    fake_feishu = FakeFeishuClient()
    with patch("app.services.notification_hub._ws_push", side_effect=FakeWsPush.fake_push), \
         patch.object(hub, "_feishu", fake_feishu):
        await hub.notify_status_change(
            feature_id="feat-123",
            old_status="pending",
            new_status="brainstorming",
        )

    assert len(fake_feishu.post_text_calls) == 0


@pytest.mark.asyncio
async def test_notify_status_change_skips_feishu_when_disabled() -> None:
    """Feishu is NOT called when include_feishu=False."""
    FakeWsPush.reset()
    FakeFeishuClient.reset()

    hub = NotificationHub(include_feishu=False)
    fake_feishu = FakeFeishuClient()
    with patch("app.services.notification_hub._ws_push", side_effect=FakeWsPush.fake_push), \
         patch.object(hub, "_feishu", fake_feishu):
        await hub.notify_status_change(
            feature_id="feat-123",
            old_status="pending",
            new_status="brainstorming",
            feature_title="Any title",
        )

    assert len(fake_feishu.post_text_calls) == 0


@pytest.mark.asyncio
async def test_notify_status_change_feishu_failure_does_not_raise() -> None:
    """If Feishu post_text returns False, no exception propagates."""
    FakeWsPush.reset()
    FakeFeishuClient.reset()
    FakeFeishuClient.should_fail = True

    hub = NotificationHub(include_feishu=True)
    fake_feishu = FakeFeishuClient()
    with patch("app.services.notification_hub._ws_push", side_effect=FakeWsPush.fake_push), \
         patch.object(hub, "_feishu", fake_feishu):
        # Must not raise
        await hub.notify_status_change(
            feature_id="feat-123",
            old_status="pending",
            new_status="brainstorming",
            feature_title="Title",
        )

    assert len(FakeWsPush.calls) == 1  # WS still delivered


# ---------------------------------------------------------------------------
# notify_log
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_notify_log_only_pushes_ws() -> None:
    """Log events go only to WebSocket, never to Feishu."""
    FakeWsPush.reset()
    FakeFeishuClient.reset()

    hub = NotificationHub(include_feishu=True)
    fake_feishu = FakeFeishuClient()
    with patch("app.services.notification_hub._ws_push", side_effect=FakeWsPush.fake_push), \
         patch.object(hub, "_feishu", fake_feishu):
        await hub.notify_log(
            feature_id="feat-456",
            stage="implementing",
            line="$ pip install httpx",
        )

    assert len(FakeWsPush.calls) == 1
    assert FakeWsPush.calls[0]["event"]["type"] == "log"
    assert FakeWsPush.calls[0]["event"]["line"] == "$ pip install httpx"
    assert len(fake_feishu.post_text_calls) == 0


# ---------------------------------------------------------------------------
# notify_stage_complete
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_notify_stage_complete_only_pushes_ws() -> None:
    """stage_complete events go only to WebSocket."""
    FakeWsPush.reset()
    FakeFeishuClient.reset()

    hub = NotificationHub(include_feishu=True)
    fake_feishu = FakeFeishuClient()
    result_data = {"summary": "Generated 3 tasks"}
    with patch("app.services.notification_hub._ws_push", side_effect=FakeWsPush.fake_push), \
         patch.object(hub, "_feishu", fake_feishu):
        await hub.notify_stage_complete(
            feature_id="feat-789",
            stage="planning",
            result=result_data,
        )

    assert len(FakeWsPush.calls) == 1
    assert FakeWsPush.calls[0]["event"]["type"] == "stage_complete"
    assert FakeWsPush.calls[0]["event"]["result"] == result_data
    assert len(fake_feishu.post_text_calls) == 0


# ---------------------------------------------------------------------------
# notify_awaiting_approval
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_notify_awaiting_approval_pushes_ws_and_feishu() -> None:
    """awaiting_approval events push to both WebSocket and Feishu."""
    FakeWsPush.reset()
    FakeFeishuClient.reset()

    hub = NotificationHub(include_feishu=True)
    fake_feishu = FakeFeishuClient()
    with patch("app.services.notification_hub._ws_push", side_effect=FakeWsPush.fake_push), \
         patch.object(hub, "_feishu", fake_feishu):
        await hub.notify_awaiting_approval(
            feature_id="feat-abc",
            stage="brainstorming",
            message="请在浏览器确认 Brainstorming 结果",
        )

    assert len(FakeWsPush.calls) == 1
    assert FakeWsPush.calls[0]["event"]["type"] == "awaiting_approval"
    assert len(fake_feishu.post_text_calls) == 1
    assert "brainstorming" in fake_feishu.post_text_calls[0]


# ---------------------------------------------------------------------------
# notify_error
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_notify_error_pushes_ws_and_feishu() -> None:
    """Error events push to both WebSocket and Feishu."""
    FakeWsPush.reset()
    FakeFeishuClient.reset()

    hub = NotificationHub(include_feishu=True)
    fake_feishu = FakeFeishuClient()
    with patch("app.services.notification_hub._ws_push", side_effect=FakeWsPush.fake_push), \
         patch.object(hub, "_feishu", fake_feishu):
        await hub.notify_error(
            feature_id="feat-def",
            stage="implementing",
            message="subprocess timeout after 300s",
        )

    assert len(FakeWsPush.calls) == 1
    assert FakeWsPush.calls[0]["event"]["type"] == "error"
    assert len(fake_feishu.post_text_calls) == 1
    assert "implementing" in fake_feishu.post_text_calls[0]
    assert "subprocess timeout" in fake_feishu.post_text_calls[0]


# ---------------------------------------------------------------------------
# _format_feishu_status_change
# ---------------------------------------------------------------------------


def test_format_feishu_status_change() -> None:
    """_format_feishu_status_change produces the expected message format."""
    text = NotificationHub._format_feishu_status_change(
        feature_title="登录功能",
        old_status="pending",
        new_status="brainstorming",
    )
    assert text == "[solo100] Feature「登录功能」状态变更：pending → brainstorming"


# ---------------------------------------------------------------------------
# include_feishu=False disables Feishu entirely
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_include_feishu_false_suppresses_all_feishu_calls() -> None:
    """When include_feishu=False, no Feishu call is made for any event type."""
    FakeWsPush.reset()
    FakeFeishuClient.reset()

    hub = NotificationHub(include_feishu=False)
    fake_feishu = FakeFeishuClient()
    with patch("app.services.notification_hub._ws_push", side_effect=FakeWsPush.fake_push), \
         patch.object(hub, "_feishu", fake_feishu):
        await hub.notify_awaiting_approval("f1", "planning", "msg")
        await hub.notify_error("f1", "planning", "err")

    assert len(FakeWsPush.calls) == 2
    assert len(fake_feishu.post_text_calls) == 0
```

**Commit:**

```bash
git add backend/app/services/__init__.py \
         backend/app/services/notification_hub.py \
         backend/tests/unit/test_notification_hub.py
git commit -m "feat: add NotificationHub as unified event dispatcher

添加 app/services/notification_hub.py：薄封装，复用 push_feature_event 分发 WebSocket 事件，
按事件类型决定是否推送飞书（log/stage_complete 仅 WebSocket；status_change/
awaiting_approval/error 同时推送飞书）。失败静默，不阻塞主流程。
添加完整单元测试，覆盖所有事件类型、所有分支路径
"
```

---

## Task 3: 集成文档 — 业务层调用指南

**Files**
- 创建: `backend/docs/notification-hub-integration.md`（供 FeatureExecutor/ApprovalGateway 实现者参考）

### 步骤 3.1 创建 `backend/docs/notification-hub-integration.md`

```markdown
# NotificationHub 集成指南

本文档说明业务层（FeatureExecutor、ApprovalGateway）如何调用 NotificationHub。

## 导入

```python
from app.services.notification_hub import notification_hub
```

`singleton` 实例在模块加载时创建，所有协程共享同一个实例。

## 调用速查表

| 场景 | 调用方式 | WebSocket | 飞书 |
|------|----------|-----------|------|
| Feature 状态变更 | `notify_status_change(...)` | Yes | Yes（需传 feature_title）|
| Agent stdout/stderr 日志 | `notify_log(...)` | Yes | No |
| 阶段执行完成 | `notify_stage_complete(...)` | Yes | No |
| 等待人工确认 | `notify_awaiting_approval(...)` | Yes | Yes |
| 执行出错 | `notify_error(...)` | Yes | Yes |

## 示例：FeatureExecutor 状态变更

```python
async def _transition(self, feature_id: str, new_status: str, title: str = "") -> None:
    old_status = self._current_status
    self._current_status = new_status

    # Update DB ...
    await self._db.flush()

    # Notify all channels
    await notification_hub.notify_status_change(
        feature_id=feature_id,
        old_status=old_status,
        new_status=new_status,
        feature_title=title,        # 传空则飞书不推送
    )
```

## 示例：流式日志推送

```python
async def _stream_log(self, feature_id: str, stage: str, line: str) -> None:
    # 每行日志实时推送，高频调用，飞书不接收
    await notification_hub.notify_log(
        feature_id=feature_id,
        stage=stage,
        line=line.rstrip("\n"),
    )
```

## 测试中替换 NotificationHub

在单元测试中用 `unittest.mock.patch` 替换 `notification_hub`：

```python
mock_hub = AsyncMock(spec=NotificationHub)
with patch("app.services.feature_executor.notification_hub", mock_hub):
    await executor.run()
    mock_hub.notify_status_change.assert_awaited_once_with(...)
```

## 禁用飞书通知

测试环境可禁用飞书：

```python
from app.services.notification_hub import NotificationHub

hub = NotificationHub(include_feishu=False)   # 仅 WebSocket
hub = NotificationHub(feishu_webhook_url="")  # 等效：webhook URL 为空时不发送
```

## 注意事项

1. **飞书仅单向**：NotificationHub 不接收飞书响应，不实现任何回调。
2. **日志频率**：Agent 日志（notify_log）可能每秒数十条，仅走 WebSocket 通道。
3. **Feishu 超时**：HTTP POST 超时固定 5 秒，失败时记录 WARNING 日志后继续。
4. **时间戳**：timestamp 由 `push_feature_event` 统一注入，业务层无需处理。
```

**Commit:**

```bash
git add backend/docs/notification-hub-integration.md
git commit -m "docs: add NotificationHub integration guide for business-layer developers

添加 backend/docs/notification-hub-integration.md：调用速查表、代码示例、测试替换方式、
注意事项，供 FeatureExecutor 和 ApprovalGateway 实现时参考
"
```

---

## Task 4: 集成测试 — NotificationHub + WebSocket 端到端

**Files**
- 创建: `backend/tests/unit/test_notification_hub_ws_integration.py`

### 步骤 4.1 创建 `backend/tests/unit/test_notification_hub_ws_integration.py`

```python
"""Integration-style test: wire NotificationHub to the real _active_connections dict.

This test starts a real async task that calls notification_hub, while a real
WebSocket client connects to the FastAPI WebSocket endpoint and asserts the
messages arrive correctly.

Requires the full app stack (routers loaded) so it runs against the AsyncClient
fixture from conftest.
"""

import asyncio
import json
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.notification_hub import NotificationHub


@pytest.mark.asyncio
async def test_notification_hub_delivers_status_change_to_ws_client() -> None:
    """
    Start a background task that calls notification_hub.notify_status_change,
    then connect a WebSocket client and verify it receives the event.
    """
    feature_id = "test-feat-ws-001"
    received_events: list[dict[str, Any]] = []

    async def _push_task() -> None:
        """Background coroutine that fires the notification."""
        hub = NotificationHub(include_feishu=False)  # disable Feishu to isolate WebSocket
        await hub.notify_status_change(
            feature_id=feature_id,
            old_status="pending",
            new_status="brainstorming",
            feature_title="WS Integration Test",
        )

    async def _ws_reader() -> None:
        """Read one message from the real WebSocket endpoint."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as http_client:
            async with http_client.client.ws_connect(f"/ws/features/{feature_id}") as ws:
                msg = await ws.receive_text()
                received_events.append(json.loads(msg))

    # Run both tasks concurrently; give ws_reader time to connect first
    await _ws_reader()
    await _push_task()

    # Allow a small tick for the event to propagate
    await asyncio.sleep(0.1)

    assert len(received_events) == 1
    event = received_events[0]
    assert event["type"] == "status_change"
    assert event["feature_id"] == feature_id
    assert event["old_status"] == "pending"
    assert event["new_status"] == "brainstorming"
    assert "timestamp" in event


@pytest.mark.asyncio
async def test_notification_hub_delivers_log_lines_to_ws_client() -> None:
    """
    Push three log lines via notify_log and verify all three arrive via WebSocket
    in the correct order.
    """
    feature_id = "test-feat-ws-002"
    received_events: list[dict[str, Any]] = []

    async def _push_logs() -> None:
        hub = NotificationHub(include_feishu=False)
        for line in ["$ git clone git@github.com:test/repo.git", "Cloning into 'repo'..."]:
            await hub.notify_log(feature_id=feature_id, stage="implementing", line=line)
        await hub.notify_stage_complete(
            feature_id=feature_id,
            stage="implementing",
            result={"files_changed": 3},
        )

    async def _ws_reader() -> None:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as http_client:
            async with http_client.client.ws_connect(f"/ws/features/{feature_id}") as ws:
                # Read all 3 events (2 log + 1 stage_complete)
                for _ in range(3):
                    msg = await ws.receive_text()
                    received_events.append(json.loads(msg))

    # Start reader first so the WS connection is registered before we push
    await _ws_reader()
    await _push_logs()
    await asyncio.sleep(0.1)

    assert len(received_events) == 3
    assert received_events[0]["type"] == "log"
    assert received_events[0]["line"] == "$ git clone git@github.com:test/repo.git"
    assert received_events[1]["type"] == "log"
    assert received_events[1]["line"] == "Cloning into 'repo'..."
    assert received_events[2]["type"] == "stage_complete"
    assert received_events[2]["result"] == {"files_changed": 3}


@pytest.mark.asyncio
async def test_notification_hub_error_type_and_timestamp() -> None:
    """
    Send an error notification and verify type + timestamp fields are present.
    """
    feature_id = "test-feat-ws-003"
    received_events: list[dict[str, Any]] = []

    async def _push_error() -> None:
        hub = NotificationHub(include_feishu=False)
        await hub.notify_error(
            feature_id=feature_id,
            stage="testing",
            message="pytest failed: 2 tests failed, 10 passed",
        )

    async def _ws_reader() -> None:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as http_client:
            async with http_client.client.ws_connect(f"/ws/features/{feature_id}") as ws:
                msg = await ws.receive_text()
                received_events.append(json.loads(msg))

    await _ws_reader()
    await _push_error()
    await asyncio.sleep(0.1)

    assert len(received_events) == 1
    event = received_events[0]
    assert event["type"] == "error"
    assert event["feature_id"] == feature_id
    assert event["stage"] == "testing"
    assert "timestamp" in event
```

**Commit:**

```bash
git add backend/tests/unit/test_notification_hub_ws_integration.py
git commit -m "test: add WebSocket integration tests for NotificationHub

添加 test_notification_hub_ws_integration.py：启动真实 WebSocket 连接，
验证 status_change/log/stage_complete/error 消息端到端从 NotificationHub
到达浏览器客户端，包含时间戳字段验证
"
```

---

## Task 5: 最终验证

### 步骤 5.1 语法检查

```bash
cd /home/codingdie/codes/solo100/backend && \
  python -m py_compile \
    app/services/__init__.py \
    app/services/feishu_client.py \
    app/services/notification_hub.py && echo "Syntax OK"
```

### 步骤 5.2 运行所有单元测试

```bash
cd /home/codingdie/codes/solo100/backend && \
  PYTHONPATH=. pytest tests/unit/test_feishu_client.py \
                       tests/unit/test_notification_hub.py \
                       tests/unit/test_notification_hub_ws_integration.py \
                       -v --tb=short 2>&1 | tail -60
```

预期：所有测试 PASSED（test_feishu_client: 7 passed，test_notification_hub: 10 passed，
test_notification_hub_ws_integration: 3 passed）。

### 步骤 5.3 检查 NotificationHub 可被正常导入

```bash
cd /home/codingdie/codes/solo100/backend && \
  PYTHONPATH=. python -c \
    "from app.services.notification_hub import notification_hub, NotificationHub; \
     from app.services.feishu_client import feishu_client; \
     print('import ok'); \
     print('feishu_client.is_configured:', feishu_client.is_configured)"
```

预期输出：两行，无 ImportError。

### 步骤 5.4 提交最终 Commit

```bash
git add -A
git status
# 确认新增文��：app/services/、tests/unit/test_feishu_client.py、
#              tests/unit/test_notification_hub.py、
#              tests/unit/test_notification_hub_ws_integration.py、
#              docs/notification-hub-integration.md
git commit -m "feat: complete NotificationHub implementation with Feishu + WebSocket channels

Task 5 验证步骤：语法编译通过、pytest 全部通过（20 tests）、
NotificationHub 可正常导入。通知层实现完成
"
```

---

## 顺序依赖关系

```
plan-1 (backend-foundation)
    │
    ├── app/config.py          (feishu_webhook_url)
    ├── app/routers/websocket.py  (push_feature_event)
    └── requirements.txt      (httpx)
              │
              ▼
      Task 1 (FeishuClient)  ─── test_feishu_client.py
                    │
                    ▼
      Task 2 (NotificationHub) ─── test_notification_hub.py
                    │
                    ▼
      Task 3 (integration docs)
                    │
                    ▼
      Task 4 (WS integration test)
                    │
                    ▼
      Task 5 (verification)
```

---

## 风险与注意事项

1. **WebSocket 连接内存存储**：`_active_connections` 是进程内字典，多 worker 部署（`uvicorn --workers > 1`）时连接分布在不同进程，部分客户端收不到消息。当前阶段接受此限制，后续接入 Redis pub/sub 后统一修复。
2. **飞书 webhook URL 泄露风险**：`settings.feishu_webhook_url` 来自环境变量，必须确保 `.env` 不提交到 Git（`.env.example` 中该字段为空字符串作为示例）。
3. **Feishu API 配额**：飞书 Incoming Webhook 每人每分钟最多 20 条请求。若 FeatureExecutor 短时间内推送大量事件（如流式日志），不应走飞书通道（`notify_log` 已排除飞书）。`notify_status_change` 在正常流程中每 Feature 最多十余次，不会触发限流。
4. **测试中 mock 层级**：`test_notification_hub.py` 通过 `patch.object(hub, "_feishu", fake)` 替换飞书客户端，确保飞书 HTTP 调用不发出。若后续 FeishuClient 接口变更，只需更新此处 mock。
5. **NotificationHub 单例 vs 多实例**：生产代码使用 `notification_hub` 单例。测试代码可通过 `NotificationHub(include_feishu=False)` 创建隔离实例，避免干扰。

---

### Critical Files for Implementation

- `backend/app/services/feishu_client.py`
- `backend/app/services/notification_hub.py`
- `backend/app/routers/websocket.py`
- `backend/tests/unit/test_notification_hub.py`
- `backend/tests/unit/test_feishu_client.py`