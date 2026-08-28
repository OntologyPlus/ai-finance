from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import List
import json
from loguru import logger

router = APIRouter()


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket connected, total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"WebSocket disconnected, total: {len(self.active_connections)}")

    async def send_personal_message(self, message: dict, websocket: WebSocket):
        await websocket.send_text(json.dumps(message, ensure_ascii=False, default=str))

    async def broadcast(self, message: dict):
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(json.dumps(message, ensure_ascii=False, default=str))
            except Exception:
                disconnected.append(connection)
        for conn in disconnected:
            self.disconnect(conn)

    async def send_alert(self, alert_data: dict):
        await self.broadcast({"type": "alert", "data": alert_data})

    async def send_approval(self, approval_data: dict):
        await self.broadcast({"type": "approval", "data": approval_data})

    async def send_notification(self, notification_data: dict):
        await self.broadcast({"type": "notification", "data": notification_data})


ws_manager = ConnectionManager()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                msg_type = msg.get("type", "ping")
                if msg_type == "ping":
                    await ws_manager.send_personal_message({"type": "pong"}, websocket)
            except json.JSONDecodeError:
                await ws_manager.send_personal_message(
                    {"type": "error", "message": "Invalid JSON"}, websocket
                )
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
