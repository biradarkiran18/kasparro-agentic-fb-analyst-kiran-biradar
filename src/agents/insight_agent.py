"""
Insight agent: produce candidate hypotheses from a summary and baselines.

Responsibilities:
- Inspect summary + baseline evidence
- Produce targeted, evidence-backed hypotheses (not generic statements)
- Include metadata: id, hypothesis text, metrics_used, initial_confidence, evidence_hint
"""
from __future__ import annotations

from typing import Any, Dict, List
import uuid

from src.utils.baseline import evidence_from_summary_and_baseline
from src.utils.observability import log_event, log_decision, log_agent_io
from src.utils.llm_validation import (
    validate_hypothesis_output,
    sanitize_hypothesis_output
)


def _make_id() -> str:
    return str(uuid.uuid4())[:8]


def generate_insights(
    summary: Dict[str, Any],
    baseline: Dict[str, Any],
    *,
    top_k: int = 5,
    base_dir: str = "logs/observability",
) -> List[Dict[str, Any]]:
    """
    Generate a short list of prioritized hypotheses with pointers to evidence.

    Each hypothesis:
    {
      "id": str,
      "hypothesis": str,
      "metrics_used": ["ctr","roas"],
      "initial_confidence": float,
      "evidence_hint": {...}  # small summary of evidence to help evaluator
    }
    """
    log_event("insight_agent", "generate_started", {"has_summary": bool(summary)}, base_dir=base_dir)

    # Log input summary
    input_summary = {
        "has_baseline": bool(baseline),
        "summary_keys": list(summary.keys()) if summary else [],
        "num_campaigns": len(summary.get("by_campaign", [])) if summary else 0,
    }

    out: List[Dict[str, Any]] = []

    try:
        # build consolidated evidence
        ev = evidence_from_summary_and_baseline(summary, baseline or {})
    except Exception as e:
        ev = {}
        log_event("insight_agent", "evidence_error", {"error": str(e)}, base_dir=base_dir)

    # prioritize by magnitude of ROAS delta, then CTR delta
    roas_delta = ev.get("roas_delta_pct", 0.0) or 0.0
    ctr_delta = ev.get("ctr_delta_pct", 0.0) or 0.0

    # If large roas decline, create ROAS-specific hypotheses
    if roas_delta < -0.05:
        text = f"ROAS has declined by {round(roas_delta*100,1)}% vs baseline; investigate budget/creative/traffic"
        h = {
            "id": _make_id(),
            "hypothesis": text,
            "metrics_used": ["roas", "ctr"],
            "initial_confidence": min(0.9, max(0.2, abs(roas_delta))),
            "evidence_hint": {"roas_delta_pct": float(roas_delta)},
        }
        out.append(h)

        # Log decision
        log_decision(
            "insight_agent",
            "generated_roas_hypothesis",
            (
                f"ROAS delta ({roas_delta:.2%}) exceeded threshold (-5%), "
                "indicating performance degradation"
            ),
            {
                "roas_delta_pct": float(roas_delta),
                "threshold": -0.05,
                "hypothesis_id": h["id"],
            },
            base_dir=base_dir
        )

    # If CTR shows a decline, produce creative fatigue hypothesis
    if ctr_delta < -0.05:
        text = (
            f"CTR has dropped by {round(ctr_delta*100,1)}% vs baseline — "
            "possible creative fatigue or targeting issue"
        )
        h = {
            "id": _make_id(),
            "hypothesis": text,
            "metrics_used": ["ctr"],
            "initial_confidence": min(0.85, max(0.2, abs(ctr_delta))),
            "evidence_hint": {"ctr_delta_pct": float(ctr_delta)},
        }
        out.append(h)

        # Log decision
        log_decision(
            "insight_agent",
            "generated_ctr_hypothesis",
            (
                f"CTR delta ({ctr_delta:.2%}) exceeded threshold (-5%), "
                "suggesting creative fatigue"
            ),
            {
                "ctr_delta_pct": float(ctr_delta),
                "threshold": -0.05,
                "hypothesis_id": h["id"],
            },
            base_dir=base_dir
        )

    # If both metrics ok but sample small, produce a small-sample hypothesis
    rows_used = int(ev.get("rows_used_for_baseline", 0))
    if rows_used < 7:
        text = "Sample size for baseline is small — results may be noisy; gather more data or widen baseline window"
        out.append(
            {
                "id": _make_id(),
                "hypothesis": text,
                "metrics_used": ["ctr", "roas"],
                "initial_confidence": 0.25,
                "evidence_hint": {"rows_used_for_baseline": rows_used},
            }
        )

    # Additional generic but evidence-linked recommendations (kept short)
    # e.g., if roas drop is large and creatives are few -> suggest creative refresh
    num_creatives = summary.get("global", {}).get("num_creatives", None)
    if roas_delta < -0.20 and (num_creatives is not None and num_creatives < 2):
        text = (
            "Significant ROAS drop with few creatives detected — "
            "try fresh creative variants targeted at top segments"
        )
        out.append(
            {
                "id": _make_id(),
                "hypothesis": text,
                "metrics_used": ["roas"],
                "initial_confidence": 0.8,
                "evidence_hint": {
                    "roas_delta_pct": float(roas_delta),
                    "num_creatives": num_creatives
                },
            }
        )

    # dedupe and limit to top_k by confidence
    # assign a simple score = initial_confidence (fallback 0.3)
    scored = []
    seen_texts = set()
    for h in out:
        t = (h.get("hypothesis") or "").strip()
        if not t or t in seen_texts:
            continue
        seen_texts.add(t)
        scored.append((h.get("initial_confidence", 0.3), h))
    scored.sort(key=lambda x: x[0], reverse=True)
    selected = [h for _, h in scored][:top_k]

    # Validate output structure
    try:
        is_valid, errors = validate_hypothesis_output(
            selected,
            min_confidence=0.0,
            max_confidence=1.0
        )

        if not is_valid:
            log_event(
                "insight_agent",
                "validation_warning",
                {"errors": errors, "num_hypotheses": len(selected)},
                base_dir=base_dir
            )

            # Attempt to sanitize
            selected = sanitize_hypothesis_output(
                selected,
                fix_confidence=True,
                fix_missing_fields=True,
                default_confidence=0.5
            )

            log_event(
                "insight_agent",
                "output_sanitized",
                {"num_hypotheses": len(selected)},
                base_dir=base_dir
            )
    except Exception as e:
        log_event(
            "insight_agent",
            "validation_error",
            {"error": str(e)},
            base_dir=base_dir
        )

    # Log output summary
    output_summary = {
        "hypotheses_generated": len(selected),
        "avg_confidence": sum(h.get("initial_confidence", 0) for h in selected) / max(1, len(selected)),
        "metrics_coverage": list(set(m for h in selected for m in h.get("metrics_used", []))),
    }
    log_agent_io("insight_agent", input_summary, output_summary, base_dir=base_dir)

    log_event("insight_agent", "generate_completed", {"generated": len(selected)}, base_dir=base_dir)
    return selected


def generate_hypotheses(
    summary: Dict[str, Any],
    tasks: List[Any],
    cfg: Dict[str, Any],
    *,
    base_dir: str = "logs/observability"
) -> List[Dict[str, Any]]:
    """
    Wrapper for generate_insights to match orchestrator's expected signature.
    The tasks parameter is ignored as it's not needed for hypothesis generation.
    """
    # Extract baseline from cfg if available
    baseline = cfg.get("roas_baseline", {})
    top_k = cfg.get("top_k_insights", 5)
    return generate_insights(summary, baseline, top_k=top_k, base_dir=base_dir)
