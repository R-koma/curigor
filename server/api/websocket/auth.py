import json
from typing import NamedTuple

from fastapi import WebSocket

from core.auth import verify_jwt


class WebSocketAuth(NamedTuple):
    user_id: str
    protocol_version: int | None


async def authenticate_websocket(websocket: WebSocket) -> WebSocketAuth:
    """接続後、最初のメッセージで JWT を検証し、user_id とクライアントの版を返す。失敗時は接続を閉じる。"""
    raw = await websocket.receive_text()

    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        await websocket.close(code=4001, reason="Invalid message format")
        raise ValueError("Invalid message format") from None

    if data.get("type") != "authenticate" or not data.get("token"):
        await websocket.close(code=4001, reason="First message must be authenticate")
        raise ValueError("First message must be authenticate")

    try:
        payload = verify_jwt(data["token"])
        user_id: str | None = payload.get("sub")
        if not user_id:
            await websocket.close(code=4003, reason="Invalid token")
            raise ValueError("Invalid token")
    except ValueError:
        await websocket.close(code=4003, reason="Invalid token")
        raise
    version = data.get("protocol_version")
    return WebSocketAuth(user_id, version if type(version) is int else None)
