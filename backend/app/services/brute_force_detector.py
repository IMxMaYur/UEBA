"""
brute_force_detector.py
------------------------
Rule-based Brute Force and Credential Stuffing Detector.

Simulates high-velocity failed login detection with IP reputation analysis.
Represents the foundational security feature layer (NIST AC/AU controls)
that provides telemetry for AI models and triggers immediate alerts.
"""

from dataclasses import dataclass
from typing import List


@dataclass
class BruteForceResult:
    detected: bool
    attack_type: str
    failed_attempts: int
    time_window_minutes: int
    source_ip: str
    ip_reputation: str
    country: str
    risk_score: float
    severity: str
    description: str


# Known malicious IP ranges for demo (simulated threat intel)
MALICIOUS_IP_POOL = [
    ("185.220.101.45",  "Tor Exit Node",       "Netherlands"),
    ("45.155.205.233",  "Known C2 Server",     "Russia"),
    ("198.96.155.3",    "Datacenter/VPN",      "United States"),
    ("92.118.160.1",    "Botnet Infrastructure","Ukraine"),
    ("103.82.22.155",   "Proxy Service",       "China"),
    ("162.247.74.74",   "Tor Network Relay",   "United States"),
]


def detect_brute_force(
    failed_attempts: int = 47,
    time_window_minutes: int = 3,
    ip_index: int = 0,
) -> BruteForceResult:
    """
    Simulate detection of a brute force or credential stuffing attack.

    Args:
        failed_attempts:      Number of failed login attempts detected
        time_window_minutes:  Time window in which attempts occurred
        ip_index:             Which malicious IP to simulate (0-5)

    Returns:
        BruteForceResult with full detection details
    """
    ip_index = ip_index % len(MALICIOUS_IP_POOL)
    ip, rep, country = MALICIOUS_IP_POOL[ip_index]

    # Determine attack type
    if failed_attempts >= 1000:
        attack_type = "CREDENTIAL_STUFFING"
        risk_score  = 0.97
        severity    = "CRITICAL"
    elif failed_attempts >= 50:
        attack_type = "DICTIONARY_ATTACK"
        risk_score  = 0.93
        severity    = "CRITICAL"
    elif failed_attempts >= 10:
        attack_type = "BRUTE_FORCE"
        risk_score  = 0.84
        severity    = "HIGH"
    else:
        attack_type = "PASSWORD_SPRAY"
        risk_score  = 0.71
        severity    = "HIGH"

    rate = failed_attempts / max(time_window_minutes, 1)
    description = (
        f"{failed_attempts} failed login attempts detected in {time_window_minutes} min "
        f"({rate:.1f}/min). Source: {ip} ({rep}, {country}). "
        f"IP blocked at edge firewall. Account lockout policy triggered."
    )

    return BruteForceResult(
        detected=True,
        attack_type=attack_type,
        failed_attempts=failed_attempts,
        time_window_minutes=time_window_minutes,
        source_ip=ip,
        ip_reputation=rep,
        country=country,
        risk_score=risk_score,
        severity=severity,
        description=description,
    )


def get_scenario_shap(result: BruteForceResult) -> List[dict]:
    """Return SHAP-style feature breakdown for brute force alert."""
    rate = result.failed_attempts / max(result.time_window_minutes, 1)
    return [
        {
            "feature": "failed_login_velocity",
            "friendly_name": "Failed Login Rate (per min)",
            "value": round(rate, 2),
            "shap_value": 0.60,
            "direction": "increases_risk",
        },
        {
            "feature": "ip_reputation_score",
            "friendly_name": "IP Reputation (Known Malicious)",
            "value": 1.0,
            "shap_value": 0.45,
            "direction": "increases_risk",
        },
        {
            "feature": "foreign_country_source",
            "friendly_name": "Login Attempt from Foreign Country",
            "value": 1.0,
            "shap_value": 0.30,
            "direction": "increases_risk",
        },
        {
            "feature": "failed_login_attempts",
            "friendly_name": "Total Failed Logins",
            "value": float(result.failed_attempts),
            "shap_value": 0.25,
            "direction": "increases_risk",
        },
    ]
