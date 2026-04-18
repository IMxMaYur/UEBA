"""
stream_producer.py
------------------
Kafka-compatible in-memory stream producer.

Reads the CERT dataset CSVs chronologically and emits individual events
into an asyncio.Queue — simulating a live Log Ingestion pipeline from
endpoints (Splunk, CrowdStrike, Windows Event Forwarder, etc.).

No Apache Kafka broker required. Uses Python's native asyncio.Queue
as the message bus, which is functionally identical for our purposes.

Topics (separate queues):
  - logon_topic:  logon/logoff events
  - device_topic: USB connect/disconnect events
  - file_topic:   file copy-to-media events
"""

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional
import pandas as pd

logger = logging.getLogger(__name__)

# Shared in-memory topic queues (module-level singletons)
logon_topic:  asyncio.Queue = asyncio.Queue(maxsize=10_000)
device_topic: asyncio.Queue = asyncio.Queue(maxsize=10_000)
file_topic:   asyncio.Queue = asyncio.Queue(maxsize=10_000)

# Stream state
_producer_task: Optional[asyncio.Task] = None
_running = False
_events_emitted = 0

DATASET_DIR = Path(__file__).resolve().parents[2] / "Dataset"


def get_stream_status() -> dict:
    return {
        "running": _running,
        "events_emitted": _events_emitted,
        "logon_queue_depth":  logon_topic.qsize(),
        "device_queue_depth": device_topic.qsize(),
        "file_queue_depth":   file_topic.qsize(),
    }


async def _emit_csv_to_queue(
    csv_path: Path,
    queue: asyncio.Queue,
    event_type: str,
    speed_multiplier: float = 500.0,
    max_events: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> int:
    """
    Load a single CSV, optionally filter by date range, and stream each row
    as a JSON-serialisable dict into the target asyncio.Queue.
    """
    global _events_emitted
    if not csv_path.exists():
        logger.warning(f"Stream producer: {csv_path.name} not found — skipping.")
        return 0

    logger.info(f"Stream producer: loading {csv_path.name} ...")
    df = pd.read_csv(csv_path, nrows=max_events or 50_000)
    df["date"] = pd.to_datetime(df["date"], format="%m/%d/%Y %H:%M:%S", errors="coerce")
    df = df.dropna(subset=["date"]).sort_values("date")

    if start_date:
        df = df[df["date"] >= pd.to_datetime(start_date)]
    if end_date:
        df = df[df["date"] <= pd.to_datetime(end_date)]

    logger.info(f"  → Streaming {len(df):,} {event_type} events ...")
    emitted = 0
    prev_ts: Optional[datetime] = None

    for _, row in df.iterrows():
        if not _running:
            break

        event = {
            "event_type": event_type,
            "user": str(row.get("user", "")),
            "pc": str(row.get("pc", "")),
            "activity": str(row.get("activity", "")),
            "timestamp": row["date"].isoformat(),
            "raw": row.dropna().to_dict(),
        }

        # Simulate time delay scaled by speed_multiplier
        if prev_ts is not None:
            real_delta = (row["date"] - prev_ts).total_seconds()
            sleep_time = max(0.0, real_delta / speed_multiplier)
            if sleep_time > 0:
                await asyncio.sleep(min(sleep_time, 0.05))  # cap at 50ms
        prev_ts = row["date"]

        try:
            queue.put_nowait(event)
            emitted += 1
            _events_emitted += 1
        except asyncio.QueueFull:
            await asyncio.sleep(0.01)  # Back-pressure: wait for consumer

    return emitted


async def start_stream(
    speed_multiplier: float = 500.0,
    max_events_per_source: int = 20_000,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
):
    """
    Main producer coroutine.  Streams logon, device, and file events
    concurrently into their respective topic queues.
    """
    global _running, _events_emitted, _producer_task
    _running = True
    _events_emitted = 0
    logger.info(
        f"=== Stream Producer STARTED  "
        f"[speed={speed_multiplier}x, max={max_events_per_source:,} events/source] ==="
    )

    logon_f  = DATASET_DIR / "augmented_logon.csv"
    if not logon_f.exists():
        logon_f = DATASET_DIR / "logon.csv"

    await asyncio.gather(
        _emit_csv_to_queue(logon_f, logon_topic, "LOGON",
                           speed_multiplier, max_events_per_source, start_date, end_date),
        _emit_csv_to_queue(DATASET_DIR / "device.csv", device_topic, "DEVICE",
                           speed_multiplier, max_events_per_source, start_date, end_date),
        _emit_csv_to_queue(DATASET_DIR / "file.csv",   file_topic,   "FILE",
                           speed_multiplier, max_events_per_source, start_date, end_date),
    )

    _running = False
    logger.info(
        f"=== Stream Producer FINISHED  [{_events_emitted:,} total events emitted] ==="
    )


def stop_stream():
    global _running
    _running = False
    logger.info("Stream producer stop requested.")
