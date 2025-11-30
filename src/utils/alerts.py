import json
import os
from typing import Dict, Any


def _ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)


def write_alert(alert: Dict[str, Any], path: str = "logs/observability/alerts.json") -> str:
    _ensure_dir(os.path.dirname(path) or ".")
    alerts = []
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                alerts = json.load(f)
        except Exception:
            alerts = []
    alert_record = dict(alert)
    alerts.append(alert_record)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(alerts, f, indent=2, default=str)
    return path


def alert_rule_roas_drop(metrics: Dict[str, Any], thresholds: Dict[str, Any]) -> Dict[str, Any]:
    # raise alert when validation rate low and roas drop above threshold or num_creatives=0
    vr = metrics.get("validation_rate") or 0.0
    num_creatives = metrics.get("num_creatives", 0)
    roas_drop_threshold = thresholds.get("roas_drop_threshold", 0.2)
    # We read roas_drop if present in metrics
    roas_drop = metrics.get("roas_drop")
    triggered = False
    reason = None
    if roas_drop is not None and roas_drop > roas_drop_threshold:
        triggered = True
        reason = f"roas_drop_exceeded:{roas_drop:.3f}"
    if vr < 0.01 and num_creatives == 0:
        triggered = True
        reason = reason or "no_creatives_and_low_validation"
    if triggered:
        return {"alerted": True, "reason": reason, "metrics": metrics}
    return {"alerted": False}
