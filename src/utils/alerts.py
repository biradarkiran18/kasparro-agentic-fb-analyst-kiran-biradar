# src/utils/alerts.py
"""
Alerting utilities and simple rule engine.

Functions:
- write_alert(alert: Dict, path: str) -> path
- alert_rule_roas_drop(metrics: Dict, thresholds: Any) -> Dict
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional


def _ensure_dir(path: Optional[str]) -> None:
    if not path:
        return
    os.makedirs(path, exist_ok=True)


def write_alert(alert: Dict[str, Any], path: str = "logs/observability/alerts.json") -> str:
    """
    Append an alert record to a JSON file. Creates parent directory as needed.
    Returns the path that was written.
    """
    dirpath = os.path.dirname(path) or "."
    _ensure_dir(dirpath)

    alerts = []
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                alerts = json.load(f)
                if not isinstance(alerts, list):
                    alerts = []
        except Exception:
            alerts = []

    rec = dict(alert)
    rec.setdefault("alerted_at", None)
    alerts.append(rec)

    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(alerts, f, indent=2, default=str)
    except Exception:
        pass

    return path


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        if v is None:
            return default
        return float(v)
    except Exception:
        return default


def alert_rule_roas_drop(metrics: Dict[str, Any], thresholds: Any) -> Dict[str, Any]:
    """
    Rule: alert when validation rate is low AND roas drop > configured threshold.

    thresholds may be either a float or a dict containing 'roas_drop_threshold'.

    Output:
    {
      "alerted": bool,
      "reason": str,
      "detail": { ... }
    }
    """
    if isinstance(thresholds, dict):
        threshold_val = _safe_float(thresholds.get("roas_drop_threshold", 0.2), 0.2)
    else:
        threshold_val = _safe_float(thresholds, 0.2)

    validation_rate = _safe_float(metrics.get("validation_rate", 0.0), 0.0)

    # prefer explicit metric keys
    roas_drop = None
    if "roas_drop" in metrics:
        roas_drop = _safe_float(metrics.get("roas_drop"))
    elif "estimated_roas_drop" in metrics:
        roas_drop = _safe_float(metrics.get("estimated_roas_drop"))
    elif isinstance(metrics.get("validation_evidence"), dict):
        ev = metrics.get("validation_evidence", {})
        roas_drop = _safe_float(ev.get("roas_drop", ev.get("ctr_delta", 0.0)))
    else:
        roas_drop = 0.0

    # rule: alert if roas_drop > threshold and validation_rate < 0.5 OR no creatives generated and roas_drop positive
    no_creatives = int(metrics.get("num_creatives", 0)) == 0
    triggered = (roas_drop > threshold_val and validation_rate < 0.5) or (no_creatives and roas_drop > threshold_val)

    reason = ""
    if triggered:
        # provide machine-friendly tokens in reason so tests/assertions can match
        if no_creatives and roas_drop > threshold_val:
            reason = (
                f"no_creatives_and_roas_drop_exceeded: roas_drop={roas_drop} "
                f"threshold={threshold_val}"
            )
        else:
            reason = (
                f"roas_drop_exceeded: roas_drop={roas_drop} exceeds "
                f"threshold={threshold_val} with low validation_rate={validation_rate}"
            )
    else:
        reason = f"no_alert: roas_drop={roas_drop}, threshold={threshold_val}, validation_rate={validation_rate}"

    out = {
        "alerted": bool(triggered),
        "reason": reason,
        "detail": {"roas_drop": roas_drop, "validation_rate": validation_rate, "threshold_used": threshold_val},
    }
    return out
