"""WebSocket router for real-time Feature event push."""

import json
from datetime import datetime
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter(tags=["websocket"])

_active_connections: dict[str, list[WebSocket]] = {}


async def _accept(websocket: WebSocket) -> None:
    """Accept a WebSocket connection."""
    await websocket.accept()


async def _send_json(websocket: WebSocket, data: dict[str, Any]) -> None:
    """Send a JSON-serialisable dict over a WebSocket."""
    await websocket.send_text(json.dumps(data, default=str))


@router.websocket("/ws/features/{feature_id}")
async def feature_websocket(websocket: WebSocket, feature_id: str) -> None:
    """Bidirectional WebSocket channel for a single Feature."""
    await _accept(websocket)
    _active_connections.setdefault(feature_id, []).append(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                payload = json.loads(data)
                if payload.get("type") == "ping":
                    await _send_json(websocket, {"type": "pong", "timestamp": datetime.utcnow().isoformat()})
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        pass
    finally:
        _active_connections.get(feature_id, []).remove(websocket)
        if not _active_connections.get(feature_id):
            _active_connections.pop(feature_id, None)


async def push_feature_event(feature_id: str, event: dict[str, Any]) -> None:
    """Utility for services to push an event to all connections for a Feature."""
    event["timestamp"] = datetime.utcnow().isoformat()
    for ws in _active_connections.get(feature_id, []):
        try:
            await _send_json(ws, event)
        except Exception:
            pass
