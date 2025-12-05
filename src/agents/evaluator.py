# src/agents/evaluator.py

from __future__ import annotations

import math
from typing import Any, Dict, List, Tuple

from src.utils.observability import log_event
from src.utils.baseline import evidence_from_summary_and_baseline
from src.utils.thresholds import compute_dynamic_thresholds


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        if v is None:
            return default
        return float(v)
    except Exception:
        return default


def _normalize_confidence(v: Any) -> float:
    """
    Ensures confidence is always between 0 and 1.
    """
    x = _safe_float(v, 0.0)
    if math.isnan(x):
        return 0.0
    return max(0.0, min(1.0, x))


def _severity_from_delta(delta: float) -> str:
    """
    Categorize severity of issue based on percent delta.
    """
    if delta == float("inf"):
        return "critical"
    if delta < -0.40:
        return "high"
    if delta < -0.20:
        return "medium"
    if delta < -0.05:
        return "low"
    return "none"


def _evaluate_one(h: Dict[str, Any], evidence: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    """
    Produces a validated hypothesis record with:
    - hypothesis
    - evidence
    - impact / severity
    - confidence
    """
    base_conf = _normalize_confidence(h.get("initial_confidence", 0.0))

    # Evidence deltas
    ctr_delta = evidence.get("ctr_delta_pct", 0.0)
    roas_delta = evidence.get("roas_delta_pct", 0.0)

    # Severity buckets
    ctr_sev = _severity_from_delta(ctr_delta)
    roas_sev = _severity_from_delta(roas_delta)

    # Choose stronger of the two
    severity_rank = {"none": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}
    impact = ctr_sev if severity_rank[ctr_sev] >= severity_rank[roas_sev] else roas_sev

    # Adjust confidence by how extreme the delta is
    adj_conf = base_conf
    if impact in ("medium", "high", "critical"):
        adj_conf = min(1.0, base_conf + 0.25)
    elif impact == "low":
        adj_conf = min(1.0, base_conf + 0.10)

    # Enforce minimum confidence threshold
    min_conf = _safe_float(cfg.get("confidence_min", 0.3))
    passed = adj_conf >= min_conf

    return {
        "id": h.get("id"),
        "hypothesis": h.get("hypothesis", ""),
        "impact": impact,
        "confidence": round(adj_conf, 4),
        "passed": passed,
        "evidence": {
            "ctr_delta_pct": ctr_delta,
            "roas_delta_pct": roas_delta,
            "last_ctr": evidence.get("last_ctr", 0.0),
            "ctr_baseline": evidence.get("ctr_baseline", 0.0),
            "last_roas": evidence.get("last_roas", 0.0),
            "roas_baseline": evidence.get("roas_baseline", 0.0),
            "rows_used_for_baseline": evidence.get("rows_used_for_baseline", 0),
        },
    }


def validate(
    hypotheses: List[Dict[str, Any]],
    summary: Dict[str, Any],
    cfg: Dict[str, Any],
    *,
    df=None,
    base_dir: str = "logs/observability"
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Full V2 evaluator:
    - computes baselines if df is provided
    - merges baseline evidence with summary
    - evaluates hypotheses using severity + confidence logic
    - logs observability events
    - returns (validated_hypotheses, metrics)
    """

    log_event(
        "evaluator",
        "validate_started",
        {"num_input_hypotheses": len(hypotheses or [])},
        base_dir=base_dir,
    )

    # Compute thresholds + baselines if df available
    dynamic = compute_dynamic_thresholds(df) if df is not None else {}
    baseline = dynamic.get("roas_baseline") or {}
    evidence = evidence_from_summary_and_baseline(summary, baseline) if baseline else {}

    validated = []
    for h in (hypotheses or []):
        try:
            validated.append(_evaluate_one(h, evidence, cfg))
        except Exception as e:
            validated.append(
                {
                    "id": h.get("id"),
                    "hypothesis": h.get("hypothesis", ""),
                    "impact": "none",
                    "confidence": 0.0,
                    "passed": False,
                    "evidence": {},
                    "error": str(e),
                }
            )

    metrics = {
        "validation_rate": (
            sum(1 for v in validated if v.get("passed")) / max(1, len(validated))
        ),
        "num_hypotheses": len(validated),
        "num_passed": sum(1 for v in validated if v.get("passed")),
        "ctr_baseline": baseline.get("ctr_baseline", 0.0),
        "roas_baseline": baseline.get("roas_baseline", 0.0),
    }

    log_event(
        "evaluator",
        "validate_completed",
        {"metrics": metrics},
        base_dir=base_dir,
    )

    return validated, metrics
