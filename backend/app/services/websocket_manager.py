"""
websocket_manager.py
--------------------
Manages WebSocket connections for real-time alert broadcasting.
All connected clients (analyst dashboards) receive instant push notifications
when new alerts are created by the simulation or detection engine.
"""

import json
import logging
from typing import List
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class WebSocketManager:
    """Manages a pool of active WebSocket connections."""

    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WS client connected. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"WS client disconnected. Total: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        """Broadcast a JSON message to all active connections."""
        text = json.dumps(message)
        dead = []
        for ws in self.active_connections:
            try:
                await ws.send_text(text)
            except Exception as e:
                logger.warning(f"WS send failed: {e}")
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

    async def broadcast_alert(
        self,
        user_id: str,
        alert_type: str,
        severity: str,
        risk_score: float,
        description: str,
        alert_id: int = None,
        narrative: str = None,
        soar_tier: int = None,
    ):
        """Convenience method to broadcast a new alert event."""
        payload = {
            "event": "NEW_ALERT",
            "user_id": user_id,
            "alert_type": alert_type,
            "severity": severity,
            "risk_score": round(risk_score, 4),
            "description": description,
            "alert_id": alert_id,
            "narrative": narrative,
            "soar_tier": soar_tier,
        }
        await self.broadcast(payload)


# Singleton instance used across the entire app
ws_manager = WebSocketManager()
