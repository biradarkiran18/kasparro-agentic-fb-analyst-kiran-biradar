import numpy as np


def validate(hypotheses, summary, thresholds):
    out = []
    by_campaign = summary["by_campaign"]

    top = sorted(by_campaign, key=lambda x: x["spend"], reverse=True)[:5]
    mean_ctr = float(np.mean([c["ctr"] for c in top])) if top else 0

    daily = summary["global"]["daily_roas"]
    roas_last = daily[-1]["roas"] if daily else 0
    roas_prev = daily[-3]["roas"] if len(daily) >= 3 else roas_last
    roas_drop = (roas_prev - roas_last) / max(roas_prev, 1e-6)

    for h in hypotheses:
        validated = None
        conf = h["initial_confidence"]
        notes = []

        if "Creative fatigue" in h["hypothesis"]:
            if mean_ctr < thresholds["ctr_low_threshold"]:
                validated = True
                conf = max(conf, 0.8)
                notes.append(f"mean_ctr={mean_ctr}")
            else:
                validated = False

        if "declined" in h["hypothesis"]:
            if roas_drop > thresholds["roas_drop_threshold"]:
                validated = True
                conf = max(conf, 0.75)
                notes.append(f"roas_drop={roas_drop}")
            else:
                validated = False

        out.append(
            {
                "id": h["id"],
                "hypothesis": h["hypothesis"],
                "validated": validated,
                "final_confidence": conf,
                "metrics_used": ["ctr", "roas"],
                "notes": notes,
            }
        )

    return out
