# src/utils/observability.py
"""
Observability helpers: per-agent event logs and metrics writer.

Functions:
- log_event(agent, event, payload, base_dir=None, filename=None) -> path
- write_metrics(metrics, path='reports/metrics.json') -> path

These functions are defensive: if base_dir is None, they default to 'logs/observability'.
They always create parent directories when writing.
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any, Dict, Optional


def _ensure_dir(path: Optional[str]) -> None:
    """
    Create directory for a given path. If path is None or empty, no-op.
    """
    if not path:
        return
    os.makedirs(path, exist_ok=True)


def _safe_iso_ts() -> str:
    return datetime.utcnow().isoformat() + "Z"


def log_event(
    agent: str,
    event: str,
    payload: Dict[str, Any],
    *,
    base_dir: Optional[str] = None,
    filename: Optional[str] = None,
) -> str:
    """
    Write a single-agent event JSON into base_dir. Returns the path written.

    - base_dir: directory to place logs. If None, defaults to "logs/observability".
    - filename: optional filename; if not provided a timestamped one will be used.
    The function is defensive: it will not raise on directory creation failures.
    """
    if base_dir is None:
        base_dir = "logs/observability"

    _ensure_dir(base_dir)

    ts = _safe_iso_ts()
    if not filename:
        safe_agent = agent.replace(" ", "_")
        filename = f"{safe_agent}_{event}_{ts}.json"

    path = os.path.join(base_dir, filename)

    rec = {
        "agent": agent,
        "event": event,
        "timestamp": ts,
        "payload": payload,
    }

    try:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(rec, fh, indent=2, default=str)
    except Exception:
        # best-effort: ignore write errors (caller may still continue)
        pass

    return path


def write_metrics(metrics: Dict[str, Any], path: str = "reports/metrics.json") -> str:
    """
    Write metrics dict to a JSON file (overwrites). Creates parent dir if needed.
    Returns the path written.
    """
    dirpath = os.path.dirname(path) or "."
    _ensure_dir(dirpath)
    try:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(metrics, fh, indent=2, default=str)
    except Exception:
        # if write fails, don't crash; caller decides next steps
        pass
    return path


def write_alert(alert: Dict[str, Any], path: str = "logs/observability/alerts.json") -> str:
    """
    Helper that delegates to alerts.write_alert when present, but keep a fallback here.
    This keeps import patterns simpler for orchestrator/evaluator to call write_alert
    from either observability or alerts module.
    """
    # inline lightweight append behaviour so callers need not import alerts directly
    dirpath = os.path.dirname(path) or "."
    _ensure_dir(dirpath)
    try:
        existing = []
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as fh:
                existing = json.load(fh)
        existing.append(alert)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(existing, fh, indent=2, default=str)
    except Exception:
        pass
    return path


def log_decision(
    agent: str,
    decision: str,
    rationale: str,
    context: Dict[str, Any],
    *,
    base_dir: Optional[str] = None
) -> str:
    """
    Log a decision made by an agent with its rationale.
    Useful for understanding "why this hypothesis was generated" or "why this creative was chosen".

    Args:
        agent: Name of the agent making the decision
        decision: Brief description of what was decided
        rationale: Explanation of why this decision was made
        context: Supporting data/evidence for the decision
        base_dir: Directory for logs

    Returns:
        Path to log file
    """
    payload = {
        "decision": decision,
        "rationale": rationale,
        "context": context,
    }
    return log_event(agent, "decision", payload, base_dir=base_dir)


def log_agent_io(
    agent: str,
    inputs: Dict[str, Any],
    outputs: Dict[str, Any],
    *,
    base_dir: Optional[str] = None
) -> str:
    """
    Log input and output summaries for an agent execution.
    Helps track data flow and debug issues.

    Args:
        agent: Name of the agent
        inputs: Summary of inputs (e.g., {"summary_rows": 100, "baseline_ctr": 0.02})
        outputs: Summary of outputs (e.g., {"hypotheses_generated": 5, "avg_confidence": 0.7})
        base_dir: Directory for logs

    Returns:
        Path to log file
    """
    payload = {
        "inputs": inputs,
        "outputs": outputs,
    }
    return log_event(agent, "io_summary", payload, base_dir=base_dir)


def write_json_report(path: str, data: Any) -> str:
    """
    Write a JSON report to disk. Creates parent directories if needed.

    Args:
        path: Destination file path
        data: Data to write (will be JSON-serialized)

    Returns:
        Path to written file
    """
    dirpath = os.path.dirname(path) or "."
    _ensure_dir(dirpath)
    try:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, default=str)
    except Exception as e:
        # Log error but don't crash
        log_event("system", "write_error", {"path": path, "error": str(e)})
    return path
