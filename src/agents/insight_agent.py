from typing import Dict, List


def generate_hypotheses(summary: Dict, confidence_min: float = 0.6) -> List[Dict]:
    hyps = []
    daily = summary.get("global", {}).get("daily_roas", []) or []

    if len(daily) >= 3:
        last = float(daily[-1].get("roas") if isinstance(daily[-1], dict) else daily[-1])
        prev = float(daily[-3].get("roas") if isinstance(daily[-3], dict) else daily[-3])
        drop = (prev - last) / max(abs(prev), 1e-9)
        hyps.append(
            {
                "id": "H1",
                "hypothesis": "ROAS has declined in the last 3 days",
                "rationale": ["computed 3-day delta", f"roas_prev={prev}", f"roas_last={last}"],
                "evidence_from_summary": [f"drop_ratio={drop}"],
                "initial_confidence": 0.8 if drop > 0.1 else 0.5,
            }
        )

    hyps.append(
        {
            "id": "H2",
            "hypothesis": "Creative fatigue in top spend campaigns",
            "rationale": ["low ctr in high spend segments"],
            "evidence_from_summary": [],
            "initial_confidence": 0.5,
        }
    )

    for h in hyps:
        if h.get("initial_confidence", 0) < confidence_min:
            h["refine_request"] = {"need": ["extra aggregates"], "reason": "low confidence"}

    return hyps
