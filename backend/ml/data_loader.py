"""
data_loader.py
--------------
Loads and lightly pre-processes CERT r4.2 raw CSV files.
Large files (http.csv, email.csv) are read in chunks with optional sampling.
"""

import os
import logging
from pathlib import Path
from typing import Optional

import pandas as pd
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

DATASET_PATH = Path(os.getenv("DATASET_PATH", "../Dataset"))
HTTP_SAMPLE_RATE = float(os.getenv("HTTP_SAMPLE_RATE", "0.10"))


def _parse_date(df: pd.DataFrame, col: str = "date") -> pd.DataFrame:
    """Parse the CERT timestamp format 'MM/DD/YYYY HH:MM:SS' into datetime."""
    df[col] = pd.to_datetime(df[col], format="%m/%d/%Y %H:%M:%S", errors="coerce")
    return df


def load_logon(path: Optional[Path] = None) -> pd.DataFrame:
    """
    logon.csv fields: id, date, user, pc, activity (Logon/Logoff)
    """
    fpath = path or DATASET_PATH / "logon.csv"
    logger.info(f"Loading logon data from {fpath} ...")
    df = pd.read_csv(fpath)
    df = _parse_date(df)
    df.rename(columns={"id": "event_id"}, inplace=True)
    logger.info(f"  → {len(df):,} logon records loaded.")
    return df


def load_device(path: Optional[Path] = None) -> pd.DataFrame:
    """
    device.csv fields: id, date, user, pc, activity (connect/disconnect)
    """
    fpath = path or DATASET_PATH / "device.csv"
    logger.info(f"Loading device data from {fpath} ...")
    df = pd.read_csv(fpath)
    df = _parse_date(df)
    df.rename(columns={"id": "event_id"}, inplace=True)
    logger.info(f"  → {len(df):,} device records loaded.")
    return df


def load_file(path: Optional[Path] = None) -> pd.DataFrame:
    """
    file.csv fields: id, date, user, pc, filename, content
    Each row = a file copied to removable media.
    """
    fpath = path or DATASET_PATH / "file.csv"
    logger.info(f"Loading file-copy data from {fpath} ...")
    df = pd.read_csv(fpath)
    df = _parse_date(df)
    df.rename(columns={"id": "event_id"}, inplace=True)
    logger.info(f"  → {len(df):,} file-copy records loaded.")
    return df


def load_email(path: Optional[Path] = None, sample_rate: float = 1.0) -> pd.DataFrame:
    """
    email.csv fields: id, date, user, pc, to, cc, bcc, from, size, attachment_count, content
    Optional sampling to manage the 1.36 GB file size.
    """
    fpath = path or DATASET_PATH / "email.csv"
    logger.info(f"Loading email data from {fpath} (sample={sample_rate:.0%}) ...")
    chunks = []
    for chunk in pd.read_csv(fpath, chunksize=50_000):
        if sample_rate < 1.0:
            chunk = chunk.sample(frac=sample_rate, random_state=42)
        chunks.append(chunk)
    df = pd.concat(chunks, ignore_index=True)
    df = _parse_date(df)
    df.rename(columns={"id": "event_id"}, inplace=True)
    logger.info(f"  → {len(df):,} email records loaded.")
    return df


def load_http(path: Optional[Path] = None, sample_rate: Optional[float] = None,
              max_rows: Optional[int] = None) -> pd.DataFrame:
    """
    http.csv fields: id, date, user, pc, url, content
    Loads at most `max_rows` rows OR up to `sample_rate` fraction of the estimated
    total row count (~28M rows). Both strategies stop reading early — no full scan.
    Default: 500,000 rows (fast, representative sample).
    """
    fpath = path or DATASET_PATH / "http.csv"
    rate  = sample_rate if sample_rate is not None else HTTP_SAMPLE_RATE

    # Estimated total rows in http.csv ≈ 28 million
    ESTIMATED_TOTAL = 28_000_000
    if max_rows is not None:
        nrows = max_rows
    else:
        nrows = max(50_000, int(ESTIMATED_TOTAL * rate))

    logger.info(f"Loading HTTP data from {fpath} (max_rows={nrows:,}) ...")
    df = pd.read_csv(fpath, nrows=nrows)
    df = _parse_date(df)
    df.rename(columns={"id": "event_id"}, inplace=True)
    logger.info(f"  → {len(df):,} HTTP records loaded.")
    return df


def load_psychometric(path: Optional[Path] = None) -> pd.DataFrame:
    """
    psychometric.csv fields: employee_name, user_id, O, C, E, A, N
    """
    fpath = path or DATASET_PATH / "psychometric.csv"
    logger.info(f"Loading psychometric data from {fpath} ...")
    df = pd.read_csv(fpath)
    logger.info(f"  → {len(df):,} psychometric records loaded.")
    return df


def load_all(
    http_sample_rate: Optional[float] = None,
    email_sample_rate: float = 1.0,
) -> dict:
    """
    Load all CERT r4.2 data sources. Returns a dict of DataFrames.
    """
    return {
        "logon": load_logon(),
        "device": load_device(),
        "file": load_file(),
        "email": load_email(sample_rate=email_sample_rate),
        "http": load_http(sample_rate=http_sample_rate),
        "psychometric": load_psychometric(),
    }
