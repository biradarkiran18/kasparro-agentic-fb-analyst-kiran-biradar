import math
from typing import List, Dict, Any, Tuple
from datetime import datetime


def _is_number(x) -> bool:
    try:
        return not math.isnan(float(x))
    except Exception:
        return False


def _safe_float(x, default: float = 0.0) -> float:
    try:
        return float(x)
    except Exception:
        return default


def validate(hypotheses, summary, thresholds) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    ctr_thresh = float(thresholds.get("ctr_low_threshold", 0.01))
    roas_drop_thresh = float(thresholds.get("roas_drop_threshold", 0.2))
    min_conf = float(thresholds.get("confidence_min", 0.5))

    out = []
    stats = {"total": 0, "validated": 0, "rules_failed": {}}

    by_campaign = summary.get("by_campaign") or []
    campaigns = by_campaign if isinstance(by_campaign, list) else []

    top = sorted(campaigns, key=lambda x: float(x.get("spend", 0)), reverse=True)[:5]
    mean_ctr = 0.0
    if top:
        ctrs = [float(c.get("ctr", 0.0)) for c in top]
        mean_ctr = sum(ctrs) / len(ctrs)

    daily = summary.get("global", {}).get("daily_roas", []) or []
    roas_last = _safe_float(daily[-1].get("roas") if daily and isinstance(daily[-1], dict)
                            else (daily[-1] if daily else 0), 0)
    roas_prev = roas_last
    if len(daily) >= 3:
        prev = daily[-3]
        roas_prev = _safe_float(prev.get("roas") if isinstance(prev, dict) else prev, roas_last)

    roas_drop = 0.0
    if roas_prev and abs(roas_prev) > 0:
        roas_drop = (roas_prev - roas_last) / max(abs(roas_prev), 1e-9)

    for h in (hypotheses or []):
        stats["total"] += 1
        reasons = []
        initial_conf = h.get("initial_confidence", h.get("confidence", 0.0))
        if not _is_number(initial_conf):
            initial_conf = 0.0
            reasons.append("confidence_not_numeric")
        conf = float(initial_conf)
        validated_flag = False
        text = (h.get("hypothesis") or "").lower()

        if "creative fatigue" in text or "creative fatigue" in text:
            if mean_ctr < ctr_thresh:
                validated_flag = True
                conf = max(conf, 0.8)
                reasons.append(f"mean_ctr_{mean_ctr:.4f}_below_thresh")
            else:
                reasons.append(f"mean_ctr_{mean_ctr:.4f}_not_below_thresh")

        if any(k in text for k in ("declin", "drop", "roas")):
            if roas_drop > roas_drop_thresh:
                validated_flag = True
                conf = max(conf, 0.75)
                reasons.append(f"roas_drop_{roas_drop:.4f}_above_thresh")
            else:
                reasons.append(f"roas_drop_{roas_drop:.4f}_not_above_thresh")

        sample_indicator = summary.get("global", {}).get("total_spend") or summary.get("total_spend")
        try:
            if sample_indicator is not None and float(sample_indicator) < 10:
                conf *= 0.8
                reasons.append("small_sample_adjustment")
        except Exception:
            pass

        conf = max(0.0, min(1.0, float(conf)))
        validated_flag = validated_flag and (conf >= min_conf)

        for r in reasons:
            stats["rules_failed"].setdefault(r, 0)
            stats["rules_failed"][r] += 1
        if validated_flag:
            stats["validated"] += 1

        out.append(
            {
                "id": h.get("id"),
                "hypothesis": h.get("hypothesis"),
                "validated": bool(validated_flag),
                "final_confidence": float(conf),
                "metrics_used": ["ctr", "roas"],
                "notes": reasons,
            }
        )

    metrics = {
        "num_hypotheses": stats["total"],
        "num_validated": stats["validated"],
        "validation_rate": (stats["validated"] / stats["total"]) if stats["total"] else 0.0,
        "rules_failed_summary": stats["rules_failed"],
    }
    return out, metrics
