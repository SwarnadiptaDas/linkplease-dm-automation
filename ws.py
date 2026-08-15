import asyncio
from fastapi import WebSocket

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast_log(self, message: str, level: str = "INFO"):
        # level can be INFO, SUCCESS, WARN, ERROR
        payload = {"type": "log", "level": level, "message": message}
        for connection in self.active_connections:
            try:
                await connection.send_json(payload)
            except Exception:
                pass

    async def broadcast_stats_update(self):
        # Trigger the UI to fetch stats immediately
        payload = {"type": "update_stats"}
        for connection in self.active_connections:
            try:
                await connection.send_json(payload)
            except Exception:
                pass

manager = ConnectionManager()
