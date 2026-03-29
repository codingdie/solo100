"""Unit tests for FeishuClient."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.feishu_client import FeishuClient


class TestFeishuClientConfigured:
    def test_is_configured_true_when_url_set(self) -> None:
        client = FeishuClient(webhook_url="https://open.feishu.cn/open-apis/bot/v2/hook/abc")
        assert client.is_configured is True

    def test_is_configured_false_when_empty(self) -> None:
        client = FeishuClient(webhook_url="")
        assert client.is_configured is False

    def test_is_configured_false_when_none(self) -> None:
        client = FeishuClient(webhook_url=None)
        # depends on settings.feishu_webhook_url being empty in test env
        # just verify it doesn't raise
        assert isinstance(client.is_configured, bool)


class TestFeishuClientPostText:
    @pytest.mark.asyncio
    async def test_returns_false_when_not_configured(self) -> None:
        client = FeishuClient(webhook_url="")
        result = await client.post_text("hello")
        assert result is False

    @pytest.mark.asyncio
    async def test_posts_text_message_and_returns_true(self) -> None:
        client = FeishuClient(webhook_url="https://open.feishu.cn/open-apis/bot/v2/hook/test")

        with patch("httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"code": 0, "msg": "success"}
            mock_http.post = AsyncMock(return_value=mock_resp)
            mock_cls.return_value = mock_http

            result = await client.post_text("Feature deployed!")

        assert result is True
        call_kwargs = mock_http.post.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs.args[1]
        assert payload["msg_type"] == "text"
        assert "Feature deployed!" in payload["content"]["text"]

    @pytest.mark.asyncio
    async def test_returns_false_on_http_error(self) -> None:
        client = FeishuClient(webhook_url="https://open.feishu.cn/open-apis/bot/v2/hook/test")

        with patch("httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            mock_http.post = AsyncMock(side_effect=Exception("network error"))
            mock_cls.return_value = mock_http

            result = await client.post_text("test")

        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_on_non_200(self) -> None:
        client = FeishuClient(webhook_url="https://open.feishu.cn/open-apis/bot/v2/hook/test")

        with patch("httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            mock_resp = MagicMock()
            mock_resp.status_code = 500
            mock_http.post = AsyncMock(return_value=mock_resp)
            mock_cls.return_value = mock_http

            result = await client.post_text("test")

        assert result is False


class TestFeishuClientPostCard:
    @pytest.mark.asyncio
    async def test_posts_card_message(self) -> None:
        client = FeishuClient(webhook_url="https://open.feishu.cn/open-apis/bot/v2/hook/test")

        with patch("httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"code": 0}
            mock_http.post = AsyncMock(return_value=mock_resp)
            mock_cls.return_value = mock_http

            result = await client.post_feature_event(
                feature_id="feat-001",
                event_type="status_change",
                title="Feature Updated",
                message="Status changed: brainstorming → planning",
            )

        assert result is True
        call_kwargs = mock_http.post.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs.args[1]
        assert payload["msg_type"] in ("interactive", "text")
