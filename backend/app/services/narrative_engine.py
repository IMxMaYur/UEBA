"""
narrative_engine.py
--------------------
Generates human-readable AI analysis narratives from SHAP feature values.
No external API or LLM required — uses advanced templates that read like
a real SOC analyst's assessment. This is the "explainability" layer that
separates enterprise UEBA from academic tools.
"""

from typing import List, Dict, Optional

# ── Feature → Plain-English sentence fragments ────────────────────────────────
FEATURE_SENTENCES = {
    "file_copy_count": (
        "copied an unusually high number of files ({value:.0f}) to removable media"
    ),
    "after_hours_login_count": (
        "logged in {value:.0f} time(s) outside of normal business hours"
    ),
    "usb_connect_count": (
        "connected {value:.0f} USB device(s) — significantly above their baseline"
    ),
    "exfil_indicator": (
        "scored {value:.2f} on the exfiltration composite index (threshold: 1.0)"
    ),
    "file_sharing_visit_count": (
        "visited external file-sharing or cloud-upload sites {value:.0f} time(s)"
    ),
    "unique_pcs": (
        "accessed {value:.0f} unique workstations — indicative of lateral movement"
    ),
    "login_count": (
        "performed {value:.0f} login events, well above their daily average"
    ),
    "http_request_count": (
        "generated {value:.0f} HTTP requests — consistent with bulk data reconnaissance"
    ),
    "external_email_ratio": (
        "sent {value:.0%} of emails to external addresses"
    ),
    "suspicious_attachment_count": (
        "sent {value:.0f} email(s) with suspicious attachments"
    ),
    "behavior_spike_score": (
        "exhibited a sudden behavioral spike (score: {value:.2f})"
    ),
    "after_hours_activity_total": (
        "had {value:.0f} total after-hours activity events"
    ),
    "after_hours_usb": (
        "connected USB devices {value:.0f} time(s) after hours"
    ),
    "after_hours_file_copy": (
        "made {value:.0f} file copies outside business hours"
    ),
}

# ── Alert type → opening context ──────────────────────────────────────────────
ALERT_CONTEXT = {
    "DATA_EXFILTRATION": (
        "This user exhibits a high-confidence data exfiltration pattern. "
        "The behavioral profile is consistent with a malicious insider or "
        "compromised account actively staging sensitive data for exfiltration."
    ),
    "PRIVILEGE_ABUSE": (
        "This user has accessed systems and resources outside their normal "
        "operational scope. This pattern is consistent with privilege escalation "
        "or an insider leveraging elevated access for unauthorized purposes."
    ),
    "SUSPICIOUS_LOGIN": (
        "Anomalous authentication behavior has been detected. The login sequence "
        "does not match this user's established baseline and may indicate "
        "credential compromise or account takeover by an external actor."
    ),
    "MASS_DATA_DOWNLOAD": (
        "This user has downloaded an abnormally large volume of data from "
        "internal systems. The pattern is consistent with bulk data harvesting "
        "prior to exfiltration or resignation."
    ),
    "POTENTIAL_SABOTAGE": (
        "This user has accessed critical production systems and performed "
        "destructive or configuration-altering actions. This pattern is "
        "consistent with insider sabotage or a compromised privileged account."
    ),
    "IMPOSSIBLE_TRAVEL": (
        "Geographically impossible concurrent login activity has been detected. "
        "Two successive authentications occurred from locations that cannot be "
        "reached within the observed time delta, strongly suggesting credential theft."
    ),
    "BRUTE_FORCE": (
        "A high-velocity sequence of failed authentication attempts has been "
        "detected against this account. This pattern is consistent with an "
        "automated credential stuffing or brute-force attack."
    ),
}

# ── Severity → urgency language ───────────────────────────────────────────────
SEVERITY_LANGUAGE = {
    "CRITICAL": "IMMEDIATE ANALYST ACTION REQUIRED.",
    "HIGH":     "This warrants prompt investigation.",
    "MEDIUM":   "Further monitoring is advised.",
    "LOW":      "Flag for periodic review.",
}


def generate_narrative(
    shap_values: List[Dict],
    alert_type: str,
    severity: str,
    user_name: Optional[str] = None,
    risk_score: float = 0.0,
) -> str:
    """
    Generate a human-readable AI analysis narrative.

    Args:
        shap_values: List of SHAP dicts [{"feature": ..., "value": ..., "shap_value": ...}]
        alert_type:  e.g. "DATA_EXFILTRATION"
        severity:    e.g. "CRITICAL"
        user_name:   Optional display name
        risk_score:  Composite risk score (0-1)

    Returns:
        Multi-sentence natural language narrative string
    """
    # ── Header ──────────────────────────────────────────────────────────────
    subject = f"User {user_name}" if user_name else "This user"
    context = ALERT_CONTEXT.get(
        alert_type,
        "Anomalous behavioral patterns have been detected for this user account."
    )
    urgency = SEVERITY_LANGUAGE.get(severity.upper(), "Review recommended.")

    # ── Build evidence sentences from top SHAP features ──────────────────
    evidence_parts = []
    risk_shap = [s for s in shap_values if s.get("direction") == "increases_risk"]
    risk_shap_sorted = sorted(risk_shap, key=lambda x: abs(x.get("shap_value", 0)), reverse=True)

    for shap_entry in risk_shap_sorted[:4]:
        feat = shap_entry.get("feature", "")
        val  = shap_entry.get("value", 0)
        template = FEATURE_SENTENCES.get(feat)
        if template:
            try:
                evidence_parts.append(template.format(value=float(val)))
            except Exception:
                pass

    # ── Contribution percentages ──────────────────────────────────────────
    total_shap = sum(abs(s.get("shap_value", 0)) for s in risk_shap_sorted[:4]) or 1.0
    contributions = []
    for shap_entry in risk_shap_sorted[:3]:
        feat = shap_entry.get("feature", "")
        friendly = shap_entry.get("friendly_name", feat)
        pct = abs(shap_entry.get("shap_value", 0)) / total_shap * 100
        contributions.append(f"{friendly} ({pct:.0f}%)")

    # ── Assemble narrative ────────────────────────────────────────────────
    parts = [f"[AI ANALYSIS] {context}"]

    if evidence_parts:
        evidence_str = "; ".join(evidence_parts[:3])
        parts.append(
            f"{subject} {evidence_str}."
        )

    if contributions:
        contrib_str = ", ".join(contributions)
        parts.append(
            f"Primary risk drivers: {contrib_str}."
        )

    parts.append(
        f"Composite risk score: {risk_score:.2%}. "
        f"Severity classification: {severity}. {urgency}"
    )

    return " ".join(parts)


def generate_simple_narrative(alert_type: str, severity: str, risk_score: float) -> str:
    """Fallback narrative when SHAP data is unavailable."""
    context = ALERT_CONTEXT.get(alert_type, "Anomalous activity detected.")
    urgency = SEVERITY_LANGUAGE.get(severity.upper(), "Review recommended.")
    return (
        f"[AI ANALYSIS] {context} "
        f"Composite risk score: {risk_score:.2%}. "
        f"Severity: {severity}. {urgency}"
    )
