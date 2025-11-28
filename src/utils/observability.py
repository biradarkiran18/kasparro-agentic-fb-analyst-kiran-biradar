import os
import json
from datetime import datetime
from typing import Any, Dict


def _ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)


def log_event(agent: str, event_type: str, payload: Dict[str, Any], base_dir: str = "logs/observability") -> str:
    _ensure_dir(base_dir)
    ts = datetime.utcnow().isoformat() + "Z"
    filename = f"{agent}_{event_type}_{ts.replace(':','-')}.json"
    path = os.path.join(base_dir, filename)
    out = {"timestamp": ts, "agent": agent, "event": event_type, "payload": payload}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, default=str)
    return path


def write_metrics(metrics: Dict[str, Any], path: str = "reports/metrics.json") -> str:
    _ensure_dir(os.path.dirname(path) or ".")
    metrics_out = dict(metrics)
    metrics_out["generated_at"] = datetime.utcnow().isoformat() + "Z"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(metrics_out, f, indent=2, default=str)
    return path
