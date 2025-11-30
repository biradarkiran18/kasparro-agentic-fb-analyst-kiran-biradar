import numpy as np
from typing import List, Dict, Any, Tuple
from src.utils.observability import log_event


def _safe_get_daily_roas(summary: Dict[str, Any]):
    g = summary.get("global", {})
    return g.get("daily_roas", []) if isinstance(g, dict) else []


def validate(
    hypotheses: List[Dict[str, Any]],
    summary: Dict[str, Any],
    thresholds: Dict[str, Any],
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Validate hypotheses against the provided summary and thresholds.

    Returns:
        (validated_hypotheses, metrics)
    """
    log_event("evaluator", "validate_started", {"num_input_hypotheses": len(hypotheses or [])})
    out: List[Dict[str, Any]] = []
    by_campaign = summary.get("by_campaign", []) or []

    top = sorted(by_campaign, key=lambda x: x.get("spend", 0), reverse=True)[:5]
    mean_ctr = float(np.mean([c.get("ctr", 0) for c in top])) if top else 0.0

    daily = _safe_get_daily_roas(summary)
    roas_last = daily[-1].get("roas", 0) if daily else 0
    roas_prev = daily[-3].get("roas", roas_last) if len(daily) >= 3 else roas_last
    roas_drop = (roas_prev - roas_last) / max(roas_prev, 1e-6)

    for h in (hypotheses or []):
        validated_flag = False
        try:
            conf = float(h.get("initial_confidence", 0.5))
        except Exception:
            conf = 0.5
        notes = []

        hyp_text = str(h.get("hypothesis", "")).lower()

        if "creative fatigue" in hyp_text or ("creative" in hyp_text and "fatigue" in hyp_text):
            if mean_ctr < thresholds.get("ctr_low_threshold", 0.01):
                validated_flag = True
                conf = max(conf, 0.8)
                notes.append(f"mean_ctr={mean_ctr}")
            else:
                validated_flag = False

        if "declined" in hyp_text or "drop" in hyp_text or "decrease" in hyp_text:
            if roas_drop > thresholds.get("roas_drop_threshold", 0.2):
                validated_flag = True
                conf = max(conf, 0.75)
                notes.append(f"roas_drop={roas_drop}")
            else:
                validated_flag = bool(validated_flag)

        out.append(
            {
                "id": h.get("id"),
                "hypothesis": h.get("hypothesis"),
                "validated": validated_flag,
                "final_confidence": conf,
                "metrics_used": h.get("metrics_used", ["ctr", "roas"]),
                "notes": notes,
            }
        )

    metrics = {
        "num_hypotheses": len(hypotheses or []),
        "num_validated": sum(1 for x in out if x.get("validated")),
        "validation_rate": sum(1 for x in out if x.get("validated")) / max(len(hypotheses or []), 1),
    }

    log_event("evaluator", "validate_completed", {"metrics": metrics})
    return out, metrics
