from collections import Counter
from typing import List, Dict
from src.utils.observability import log_event


def find_low_ctr(summary: Dict, ctr_threshold: float = 0.01) -> List[Dict]:
    out = [c for c in summary.get("by_campaign", []) if c.get("ctr", 0) < ctr_threshold]
    log_event("creative_generator", "low_ctr_found", {"count": len(out)})
    return out


def generate_creatives(low_campaigns: List[Dict], df) -> List[Dict]:
    output = []
    for c in low_campaigns:
        cname = c.get("campaign_name") or c.get("campaign") or ""
        msgs = []
        if "campaign_name" in df.columns:
            msgs = df[df["campaign_name"] == cname]["creative_message"].dropna().astype(str).tolist()
        tokens = []
        for m in msgs:
            tokens += m.split()
        common = [w for w, _ in Counter(tokens).most_common(5)]
        headline = f"Stronger emphasis on {' '.join(common[:3])}".strip()
        message = "Clarify value proposition. Reinforce benefits. Increase urgency."
        cta = "Shop Now"
        output.append({"campaign": cname, "recommendations": [{"headline": headline, "message": message, "cta": cta}]})
    log_event("creative_generator", "creatives_generated", {"num": len(output)})
    return output
