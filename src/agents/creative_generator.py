from collections import Counter


def find_low_ctr(summary, ctr_threshold=0.01):
    return [c for c in summary["by_campaign"] if c["ctr"] < ctr_threshold]


def generate_creatives(low_campaigns, df):
    output = []

    for c in low_campaigns:
        cname = c["campaign_name"]
        msgs = (
            df[df["campaign_name"] == cname]["creative_message"]
            .dropna()
            .astype(str)
            .tolist()
        )

        tokens = []
        for m in msgs:
            tokens += m.split()
        common = [w for w, _ in Counter(tokens).most_common(5)]

        headline = f"Stronger emphasis on {' '.join(common[:3])}"
        message = "Clarify value proposition. Reinforce benefits. Increase urgency."
        cta = "Shop Now"

        output.append(
            {
                "campaign": cname,
                "recommendations": [
                    {"headline": headline, "message": message, "cta": cta}
                ],
            }
        )

    return output
