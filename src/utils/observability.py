import json
import os
import uuid
from datetime import datetime
from typing import Any, Dict


def _ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)


def _ts() -> str:
    return datetime.utcnow().isoformat() + "Z"


def log_event(agent: str, event_type: str, payload: Dict[str, Any], base_dir: str = "logs/observability") -> str:
    _ensure_dir(base_dir)
    ts = _ts()
    cid = payload.get("correlation_id") or str(uuid.uuid4())
    filename = f"{agent}_{event_type}_{ts.replace(':','-')}_{cid[:8]}.json"
    path = os.path.join(base_dir, filename)
    out = {"timestamp": ts, "agent": agent, "event": event_type, "correlation_id": cid, "payload": payload}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, default=str)
    return path


def write_metrics(metrics: Dict[str, Any], path: str = "reports/metrics.json") -> str:
    _ensure_dir(os.path.dirname(path) or ".")
    metrics_out = dict(metrics)
    metrics_out["metrics_version"] = metrics_out.get("metrics_version", "v1")
    metrics_out["generated_at"] = _ts()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(metrics_out, f, indent=2, default=str)
    return path


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
    alert_record["alerted_at"] = _ts()
    alerts.append(alert_record)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(alerts, f, indent=2, default=str)
    return path
