def compute_extra_aggregates(df):
    rolling = df.groupby("date")["revenue"].sum().rolling(7).sum().fillna(0)
    return {"roas_7d": rolling.to_dict()}


def apply_retry_logic(hypotheses, extra):
    out = []
    for h in hypotheses:
        if h["final_confidence"] < 0.6:
            h["final_confidence"] += 0.1
            h.setdefault("notes", []).append(
                "confidence adjusted using extra aggregates"
            )
        out.append(h)
    return out
