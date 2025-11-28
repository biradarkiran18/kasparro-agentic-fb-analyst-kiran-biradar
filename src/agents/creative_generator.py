from collections import Counter
from typing import Dict, List

DEFAULT_CTA = "Shop Now"


def find_low_ctr(summary: Dict, ctr_threshold: float = 0.01) -> List[Dict]:
    by_campaign = summary.get("by_campaign", []) or []
    return [c for c in by_campaign if float(c.get("ctr", 0.0)) < float(ctr_threshold)]


def generate_creatives(low_campaigns: List[Dict], df) -> List[Dict]:
    output = []
    for c in low_campaigns:
        cname = c.get("campaign_name")
        if not cname:
            continue
        msgs = df[df["campaign_name"] == cname].get("creative_message")
        if msgs is None:
            msgs_list = []
        else:
            msgs_list = msgs.dropna().astype(str).tolist()
        tokens = []
        for m in msgs_list:
            tokens += m.split()
        common = [w for w, _ in Counter(tokens).most_common(5)]
        headline = f"Stronger emphasis on {' '.join(common[:3])}" if common else "Reinforce product benefits"
        message = "Clarify value proposition. Reinforce benefits. Increase urgency."
        cta = DEFAULT_CTA
        output.append({"campaign": cname, "recommendations": [{"headline": headline, "message": message, "cta": cta}]})
    return output
