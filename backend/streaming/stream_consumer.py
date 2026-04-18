"""
stream_consumer.py
------------------
Kafka-compatible in-memory stream consumer.

Reads events from the asyncio.Queue topics (logon_topic, device_topic, file_topic),
maintains per-user sliding-window feature state, runs lightweight anomaly detection,
and pushes alerts via WebSocket when risk score exceeds threshold.

This replaces the batch `run_pipeline.py` with continuous real-time detection.
"""

import asyncio
import logging
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

RISK_THRESHOLD = 0.65
WINDOW_MINUTES = 60  # Sliding window duration

# Per-user sliding windows: deque of (timestamp, event_dict)
_user_windows: dict = defaultdict(lambda: deque(maxlen=500))
_consumer_task: Optional[asyncio.Task] = None
_running = False
_alerts_generated = 0
_events_processed = 0


def get_consumer_status() -> dict:
    return {
        "running": _running,
        "events_processed": _events_processed,
        "alerts_generated": _alerts_generated,
        "active_users": len(_user_windows),
    }


def _compute_window_features(window: deque, now: datetime) -> dict:
    """
    Compute behavioral features from events in the sliding window.
    Returns a feature dict compatible with risk scoring logic.
    """
    cutoff = now - timedelta(minutes=WINDOW_MINUTES)
    recent = [e for ts, e in window if ts >= cutoff]

    logon_events  = [e for e in recent if e["event_type"] == "LOGON"]
    device_events  = [e for e in recent if e["event_type"] == "DEVICE"]
    file_events    = [e for e in recent if e["event_type"] == "FILE"]

    def _after_hours(ts: str) -> bool:
        try:
            h = datetime.fromisoformat(ts).hour
            return h < 7 or h >= 19
        except Exception:
            return False

    features = {
        "login_count":             len(logon_events),
        "after_hours_login_count": sum(1 for e in logon_events if _after_hours(e["timestamp"])),
        "unique_pcs":              len({e["pc"] for e in logon_events}),
        "usb_connect_count":       sum(1 for e in device_events
                                       if "connect" in e.get("activity", "").lower()),
        "after_hours_usb":         sum(1 for e in device_events
                                       if _after_hours(e["timestamp"])),
        "file_copy_count":         len(file_events),
        "after_hours_file_copy":   sum(1 for e in file_events if _after_hours(e["timestamp"])),
        "failed_login_count":      sum(1 for e in logon_events
                                       if "fail" in e.get("activity", "").lower()),
    }

    # Derived
    features["exfil_indicator"] = (
        features["file_copy_count"] * 0.4
        + features["usb_connect_count"] * 0.3
    )
    features["after_hours_activity_total"] = (
        features["after_hours_login_count"]
        + features["after_hours_usb"]
        + features["after_hours_file_copy"]
    )
    return features


def _compute_stream_risk(features: dict) -> tuple:
    """
    Lightweight rule-based risk scoring for real-time stream events.
    Returns (risk_score 0-1, alert_type str).
    """
    score = 0.0
    alert_type = "BEHAVIORAL_ANOMALY"

    # USB + file copy at odd hours = data exfiltration
    if features["usb_connect_count"] >= 1 and features["file_copy_count"] >= 5:
        score += 0.45
        alert_type = "DATA_EXFILTRATION"

    # Many after-hours events = insider working covertly
    if features["after_hours_activity_total"] >= 3:
        score += 0.25

    # Multiple unique PCs = lateral movement
    if features["unique_pcs"] >= 4:
        score += 0.20
        alert_type = "PRIVILEGE_ABUSE"

    # High exfil indicator
    if features["exfil_indicator"] >= 3.0:
        score += 0.20

    # Brute force: many failed logins in window
    if features["failed_login_count"] >= 10:
        score += 0.50
        alert_type = "BRUTE_FORCE"

    return min(round(score, 3), 1.0), alert_type


async def _process_queue(queue: asyncio.Queue):
    """Drain one topic queue and update user windows."""
    global _events_processed
    while _running:
        try:
            event = queue.get_nowait()
            user_id = event.get("user", "UNKNOWN")
            ts_str = event.get("timestamp", "")
            try:
                ts = datetime.fromisoformat(ts_str)
            except Exception:
                ts = datetime.utcnow()

            _user_windows[user_id].append((ts, event))
            _events_processed += 1
        except asyncio.QueueEmpty:
            await asyncio.sleep(0.05)
        except Exception as e:
            logger.warning(f"Consumer queue error: {e}")
            await asyncio.sleep(0.1)


async def _risk_evaluator():
    """
    Periodically evaluates risk for all active users with sliding windows.
    Fires WebSocket alerts when risk exceeds threshold.
    """
    global _alerts_generated
    from app.services.websocket_manager import ws_manager

    while _running:
        now = datetime.utcnow()
        for user_id, window in list(_user_windows.items()):
            if not window:
                continue
            features = _compute_window_features(window, now)
            risk_score, alert_type = _compute_stream_risk(features)

            if risk_score >= RISK_THRESHOLD:
                _alerts_generated += 1
                logger.info(
                    f"[STREAM ALERT] user={user_id}  "
                    f"risk={risk_score:.2f}  type={alert_type}"
                )
                severity = "CRITICAL" if risk_score >= 0.85 else "HIGH"
                try:
                    await ws_manager.broadcast_alert(
                        user_id=user_id,
                        alert_type=f"[STREAM] {alert_type}",
                        severity=severity,
                        risk_score=risk_score,
                        description=(
                            f"Real-time stream detection: {alert_type}. "
                            f"file_copies={features['file_copy_count']}, "
                            f"usb={features['usb_connect_count']}, "
                            f"after_hours={features['after_hours_activity_total']}"
                        ),
                    )
                except Exception as e:
                    logger.warning(f"WebSocket broadcast failed: {e}")

        await asyncio.sleep(5)  # evaluate every 5 seconds


async def start_consumer():
    """Launch the consumer: processes all three topic queues + risk evaluator."""
    global _running
    _running = True
    logger.info("=== Stream Consumer STARTED ===")

    from streaming.stream_producer import logon_topic, device_topic, file_topic

    await asyncio.gather(
        _process_queue(logon_topic),
        _process_queue(device_topic),
        _process_queue(file_topic),
        _risk_evaluator(),
    )


def stop_consumer():
    global _running
    _running = False
    logger.info("Stream consumer stop requested.")
