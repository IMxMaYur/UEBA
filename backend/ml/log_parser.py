"""
log_parser.py
-------------
Normalises all CERT r4.2 raw DataFrames into a unified event schema.

Unified schema columns
-----------------------
event_id, timestamp, user, pc, event_type, sub_type, detail, date (date only)
"""

import pandas as pd


EVENT_TYPE_LOGON = "logon"
EVENT_TYPE_DEVICE = "device"
EVENT_TYPE_FILE = "file"
EVENT_TYPE_EMAIL = "email"
EVENT_TYPE_HTTP = "http"

# Known file-sharing / cloud-storage domains used to flag exfiltration risk
FILE_SHARING_DOMAINS = {
    "dropbox", "drive.google", "onedrive", "wetransfer",
    "mega.nz", "mediafire", "box.com", "sendspace",
}

AFTER_HOURS_START = 18   # 6 PM
AFTER_HOURS_END = 7      # 7 AM


def _add_date_col(df: pd.DataFrame, ts_col: str = "timestamp") -> pd.DataFrame:
    df["date"] = df[ts_col].dt.date
    return df


def _is_after_hours(ts: pd.Series) -> pd.Series:
    hour = ts.dt.hour
    return (hour >= AFTER_HOURS_START) | (hour < AFTER_HOURS_END)


# ---------------------------------------------------------------------------
# Per-source parsers
# ---------------------------------------------------------------------------

def parse_logon(df: pd.DataFrame) -> pd.DataFrame:
    """Normalise logon.csv → unified events."""
    out = pd.DataFrame()
    out["event_id"] = df["event_id"]
    out["timestamp"] = df["date"]
    out["user"] = df["user"]
    out["pc"] = df["pc"]
    out["event_type"] = EVENT_TYPE_LOGON
    out["sub_type"] = df["activity"].str.lower()   # 'logon' / 'logoff'
    out["detail"] = df["pc"]
    out["after_hours"] = _is_after_hours(df["date"])
    out = _add_date_col(out)
    return out.dropna(subset=["timestamp"])


def parse_device(df: pd.DataFrame) -> pd.DataFrame:
    """Normalise device.csv → unified events."""
    out = pd.DataFrame()
    out["event_id"] = df["event_id"]
    out["timestamp"] = df["date"]
    out["user"] = df["user"]
    out["pc"] = df["pc"]
    out["event_type"] = EVENT_TYPE_DEVICE
    out["sub_type"] = df["activity"].str.lower()   # 'connect' / 'disconnect'
    out["detail"] = df["pc"]
    out["after_hours"] = _is_after_hours(df["date"])
    out = _add_date_col(out)
    return out.dropna(subset=["timestamp"])


def parse_file(df: pd.DataFrame) -> pd.DataFrame:
    """Normalise file.csv → unified events (file copy to removable media)."""
    out = pd.DataFrame()
    out["event_id"] = df["event_id"]
    out["timestamp"] = df["date"]
    out["user"] = df["user"]
    out["pc"] = df["pc"]
    out["event_type"] = EVENT_TYPE_FILE
    out["sub_type"] = "file_copy"
    out["detail"] = df["filename"]
    out["content_keywords"] = df["content"]
    out["after_hours"] = _is_after_hours(df["date"])
    out = _add_date_col(out)
    return out.dropna(subset=["timestamp"])


def _is_file_sharing_url(url_series: pd.Series) -> pd.Series:
    """Return bool Series: True if URL matches known file-sharing domains."""
    url_lower = url_series.str.lower().fillna("")
    return url_lower.apply(
        lambda u: any(domain in u for domain in FILE_SHARING_DOMAINS)
    )


def parse_http(df: pd.DataFrame) -> pd.DataFrame:
    """Normalise http.csv → unified events."""
    out = pd.DataFrame()
    out["event_id"] = df["event_id"]
    out["timestamp"] = df["date"]
    out["user"] = df["user"]
    out["pc"] = df["pc"]
    out["event_type"] = EVENT_TYPE_HTTP
    out["sub_type"] = "http_request"
    out["detail"] = df["url"]
    out["content_keywords"] = df.get("content", "")
    out["is_file_sharing"] = _is_file_sharing_url(df["url"])
    out["after_hours"] = _is_after_hours(df["date"])
    out = _add_date_col(out)
    return out.dropna(subset=["timestamp"])


def _count_external_recipients(to_series: pd.Series, domain: str = "dtaa.com") -> pd.Series:
    """Count recipients NOT from the corporate domain."""
    def _count(val):
        if pd.isna(val):
            return 0
        addrs = str(val).split(";")
        return sum(1 for a in addrs if domain not in a.lower())
    return to_series.apply(_count)


def _count_all_recipients(series: pd.Series) -> pd.Series:
    def _count(val):
        if pd.isna(val):
            return 0
        return len(str(val).split(";"))
    return series.apply(_count)


def parse_email(df: pd.DataFrame) -> pd.DataFrame:
    """Normalise email.csv → unified events.
    Actual CERT r4.2 email columns: id, date, user, pc, to, cc, bcc, from, size, attachments, content
    """
    out = pd.DataFrame()
    out["event_id"]                = df["event_id"]
    out["timestamp"]               = df["date"]
    out["user"]                    = df["user"]
    out["pc"]                      = df["pc"]
    out["event_type"]              = EVENT_TYPE_EMAIL
    out["sub_type"]                = "email_sent"
    out["detail"]                  = df.get("to", "")
    out["email_size"]              = pd.to_numeric(df.get("size", 0), errors="coerce").fillna(0)
    # CERT r4.2 uses 'attachments' not 'attachment_count'
    attach_col = "attachments" if "attachments" in df.columns else "attachment_count"
    out["attachment_count"]        = pd.to_numeric(df.get(attach_col, 0), errors="coerce").fillna(0)
    out["recipient_count"]         = _count_all_recipients(df.get("to", pd.Series([""] * len(df))))
    out["external_recipient_count"] = _count_external_recipients(df.get("to", pd.Series([""] * len(df))))
    out["after_hours"]             = _is_after_hours(df["date"])
    out = _add_date_col(out)
    return out.dropna(subset=["timestamp"])



# ---------------------------------------------------------------------------
# Unified loader
# ---------------------------------------------------------------------------

def parse_all(raw: dict) -> dict:
    """
    Accept the dict returned by data_loader.load_all() and return
    a dict of normalised DataFrames keyed by source name.
    """
    parsed = {
        "logon": parse_logon(raw["logon"]),
        "device": parse_device(raw["device"]),
        "file": parse_file(raw["file"]),
        "email": parse_email(raw["email"]),
        "http": parse_http(raw["http"]),
    }
    return parsed
