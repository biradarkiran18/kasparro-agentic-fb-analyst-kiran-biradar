def generate_hypotheses(summary: dict, confidence_min=0.6):
    hyps = []
    daily = summary["global"]["daily_roas"]

    if len(daily) >= 3:
        last = daily[-1]["roas"]
        prev = daily[-3]["roas"]
        drop = (prev - last) / max(prev, 1e-6)
        hyps.append({
            "id": "H1",
            "hypothesis": "ROAS has declined in the last 3 days",
            "rationale": ["computed 3-day delta", f"roas_prev={prev}", f"roas_last={last}"],
            "evidence_from_summary": [f"drop_ratio={drop}"],
            "initial_confidence": 0.8 if drop > 0.1 else 0.5
        })

    hyps.append({
        "id": "H2",
        "hypothesis": "Creative fatigue in top spend campaigns",
        "rationale": ["low ctr in high spend segments"],
        "evidence_from_summary": [],
        "initial_confidence": 0.5
    })

    for h in hyps:
        if h["initial_confidence"] < confidence_min:
            h["refine_request"] = {
                "need": ["extra aggregates"],
                "reason": "low confidence"
            }

    return hyps
