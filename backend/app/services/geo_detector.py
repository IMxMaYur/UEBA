"""
geo_detector.py
---------------
Impossible Travel & Geolocation-based anomaly detection.

Detects when a user authenticates from two geographically distant locations
within a time window that makes physical travel impossible. This is one of
the most impactful demonstrations of context-aware threat detection.

Uses hardcoded city/country data for demo reliability — no external API
or internet connection required.
"""

from dataclasses import dataclass
from typing import Tuple, Optional

# ── City geo data: (city, country, lat, lon, timezone_offset_hours) ─────────
CITIES = {
    "mumbai":       ("Mumbai",          "India",          19.08,   72.88,  5.5),
    "new_york":     ("New York",        "USA",            40.71,  -74.01,  -5),
    "london":       ("London",          "UK",             51.51,   -0.13,   0),
    "beijing":      ("Beijing",         "China",          39.90,  116.40,  8),
    "sydney":       ("Sydney",          "Australia",     -33.87,  151.21, 10),
    "moscow":       ("Moscow",          "Russia",         55.75,   37.62,  3),
    "sao_paulo":    ("São Paulo",       "Brazil",        -23.55,  -46.63, -3),
    "dubai":        ("Dubai",           "UAE",            25.20,   55.27,  4),
    "singapore":    ("Singapore",       "Singapore",       1.35,  103.82,  8),
    "berlin":       ("Berlin",          "Germany",        52.52,   13.41,  1),
    "tokyo":        ("Tokyo",           "Japan",          35.68,  139.69,  9),
    "los_angeles":  ("Los Angeles",     "USA",            34.05, -118.24, -8),
}

# Pre-defined impossible travel scenarios for simulation
IMPOSSIBLE_PAIRS = [
    ("mumbai",   "new_york",  45,  "Login from Mumbai (India) followed 45 min later by login from New York (USA). Physical distance: 12,556 km. Impossible within 45 minutes."),
    ("london",   "beijing",   30,  "Login from London (UK) followed 30 min later by login from Beijing (China). Physical distance: 8,168 km. Impossible within 30 minutes."),
    ("sydney",   "moscow",    60,  "Login from Sydney (Australia) followed 60 min later by login from Moscow (Russia). Physical distance: 14,496 km. Impossible within 60 minutes."),
    ("new_york", "singapore", 20,  "Login from New York (USA) followed 20 min later by login from Singapore. Physical distance: 15,348 km. Impossible within 20 minutes."),
    ("berlin",   "tokyo",     40,  "Login from Berlin (Germany) followed 40 min later by login from Tokyo (Japan). Physical distance: 9,003 km. Impossible within 40 minutes."),
]

import random
import math


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate great-circle distance between two GPS coordinates (km)."""
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


@dataclass
class ImpossibleTravelResult:
    detected: bool
    city_a: str
    city_b: str
    country_a: str
    country_b: str
    time_delta_minutes: int
    distance_km: float
    max_possible_km: float
    description: str
    risk_score: float


def detect_impossible_travel(
    pair_index: Optional[int] = None,
) -> ImpossibleTravelResult:
    """
    Simulate an impossible travel detection event.

    Args:
        pair_index: Optional index into IMPOSSIBLE_PAIRS for deterministic demo.
                    If None, a random pair is chosen.

    Returns:
        ImpossibleTravelResult with all detection details
    """
    if pair_index is not None and 0 <= pair_index < len(IMPOSSIBLE_PAIRS):
        idx = pair_index
    else:
        idx = random.randint(0, len(IMPOSSIBLE_PAIRS) - 1)

    city_a_key, city_b_key, minutes, description = IMPOSSIBLE_PAIRS[idx]
    ca = CITIES[city_a_key]
    cb = CITIES[city_b_key]

    distance_km = _haversine_km(ca[2], ca[3], cb[2], cb[3])
    # Commercial aircraft max speed ~920 km/h
    max_possible_km = (minutes / 60.0) * 920

    return ImpossibleTravelResult(
        detected=True,
        city_a=ca[0],
        city_b=cb[0],
        country_a=ca[1],
        country_b=cb[1],
        time_delta_minutes=minutes,
        distance_km=round(distance_km, 1),
        max_possible_km=round(max_possible_km, 1),
        description=description,
        risk_score=0.88,
    )


def get_scenario_shap(result: ImpossibleTravelResult):
    """Return SHAP-style feature breakdown for impossible travel alert."""
    return [
        {
            "feature": "impossible_travel",
            "friendly_name": "Impossible Geographic Travel",
            "value": result.distance_km,
            "shap_value": 0.55,
            "direction": "increases_risk",
        },
        {
            "feature": "time_delta_minutes",
            "friendly_name": "Time Between Logins (min)",
            "value": float(result.time_delta_minutes),
            "shap_value": 0.35,
            "direction": "increases_risk",
        },
        {
            "feature": "new_country_login",
            "friendly_name": "Login from New Country",
            "value": 1.0,
            "shap_value": 0.28,
            "direction": "increases_risk",
        },
        {
            "feature": "velocity_km_per_hour",
            "friendly_name": "Required Travel Speed (km/h)",
            "value": round(result.distance_km / (result.time_delta_minutes / 60), 1),
            "shap_value": 0.22,
            "direction": "increases_risk",
        },
    ]
