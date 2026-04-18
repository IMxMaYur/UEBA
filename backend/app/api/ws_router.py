"""
ws_router.py
------------
WebSocket endpoint for real-time alert broadcasting.
Analysts on Laptop 2 connect once and immediately receive push notifications
when any simulation or detection creates a new alert on Laptop 1 (server).

Usage: ws://SERVER_IP:8000/ws/alerts
"""
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.websocket_manager import ws_manager

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])


@router.websocket("/ws/alerts")
async def websocket_alerts(websocket: WebSocket):
    """
    Real-time alert stream. Connect once, receive JSON push events.
    Event format:
        {
            "event":       "NEW_ALERT",
            "user_id":     "ACM2278",
            "alert_type":  "DATA_EXFILTRATION",
            "severity":    "CRITICAL",
            "risk_score":  0.93,
            "description": "...",
            "alert_id":    42,
            "narrative":   "...",
            "soar_tier":   3
        }
    """
    await ws_manager.connect(websocket)
    try:
        while True:
            # Keep connection alive; echo pings
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
        logger.info("WS client disconnected cleanly")
    except Exception as e:
        ws_manager.disconnect(websocket)
        logger.warning(f"WS error: {e}")
