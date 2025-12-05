"""
Creative Generator Agent: Generate actionable creative recommendations
directly tied to validated insights and evidence.

V2 Requirements:
- Creatives must reference specific diagnosed issues
- Must use evidence (deltas, segments, metrics) from insights
- NOT generic suggestions that could apply to any dataset
"""
from __future__ import annotations

from collections import Counter
from typing import List, Dict, Any, Optional
from src.utils.observability import log_event
from src.utils.llm_validation import (
    validate_creative_output,
    sanitize_creative_output
)


def _extract_campaign_keywords(df, campaign_name: str, top_n: int = 3) -> List[str]:
    """Extract common keywords from creative messages for a campaign."""
    try:
        if "campaign_name" in df.columns and "creative_message" in df.columns:
            msgs = df[df["campaign_name"] == campaign_name]["creative_message"].dropna().astype(str).tolist()
        elif "campaign" in df.columns and "creative_message" in df.columns:
            msgs = df[df["campaign"] == campaign_name]["creative_message"].dropna().astype(str).tolist()
        else:
            return []

        tokens = []
        for m in msgs:
            tokens += m.split()

        # Filter out common stop words
        stop_words = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "by"}
        tokens = [t for t in tokens if t.lower() not in stop_words and len(t) > 2]

        common = [w for w, _ in Counter(tokens).most_common(top_n)]
        return common
    except Exception as e:
        log_event("creative_generator", "keyword_extraction_error", {"error": str(e), "campaign": campaign_name})
        return []


def _generate_creative_from_insight(
    insight: Dict[str, Any],
    summary: Dict[str, Any],
    df: Any,
) -> Optional[Dict[str, Any]]:
    """
    Generate a creative recommendation tied to a specific validated insight.

    Uses evidence from the insight to create targeted recommendations.
    """
    hypothesis = insight.get("hypothesis", "")
    evidence = insight.get("evidence", {})
    impact = insight.get("impact", "none")

    # Only generate for passed insights with impact
    if not insight.get("passed") or impact == "none":
        return None

    # Extract evidence metrics
    ctr_delta = evidence.get("ctr_delta_pct", 0.0)
    roas_delta = evidence.get("roas_delta_pct", 0.0)
    ctr_baseline = evidence.get("ctr_baseline", 0.0)
    roas_baseline = evidence.get("roas_baseline", 0.0)

    # Determine primary issue
    is_ctr_issue = abs(ctr_delta) > abs(roas_delta) and ctr_delta < -0.05
    is_roas_issue = abs(roas_delta) >= abs(ctr_delta) and roas_delta < -0.05

    # Find the most affected campaigns
    by_campaign = summary.get("by_campaign", [])

    if not by_campaign:
        return None

    creatives = []

    if is_ctr_issue:
        # CTR problem - target low CTR campaigns
        low_ctr_campaigns = [
            c for c in by_campaign
            if c.get("ctr", 0) < ctr_baseline * 0.8  # 20% below baseline
        ][:3]  # Top 3

        for campaign in low_ctr_campaigns:
            camp_name = campaign.get("campaign", "Unknown")
            camp_ctr = campaign.get("ctr", 0.0)
            camp_spend = campaign.get("spend", 0.0)

            # Calculate CTR gap
            ctr_gap_pct = ((camp_ctr - ctr_baseline) / ctr_baseline * 100) if ctr_baseline > 0 else 0

            keywords = _extract_campaign_keywords(df, camp_name)
            keyword_str = ", ".join(keywords[:3]) if keywords else "key features"

            creative = {
                "campaign": camp_name,
                "issue_diagnosed": (
                    f"CTR {ctr_gap_pct:.1f}% below baseline "
                    f"({camp_ctr:.4f} vs {ctr_baseline:.4f})"
                ),
                "evidence": {
                    "current_ctr": round(camp_ctr, 4),
                    "baseline_ctr": round(ctr_baseline, 4),
                    "delta_pct": round(ctr_gap_pct, 2),
                    "campaign_spend": round(camp_spend, 2),
                },
                "recommendations": [
                    {
                        "headline": f"Refresh creative fatigue - emphasize {keyword_str}",
                        "message": (
                            f"Current CTR ({camp_ctr:.3%}) is {abs(ctr_gap_pct):.1f}% below baseline. "
                            f"Test new angles highlighting {keyword_str} with stronger social proof."
                        ),
                        "cta": "Learn More" if camp_ctr < 0.01 else "Shop Now",
                        "rationale": (
                            f"Low CTR indicates ad fatigue or poor resonance. "
                            f"Campaign has spent ${camp_spend:.0f} with declining engagement."
                        ),
                    }
                ],
                "priority": impact,
                "linked_hypothesis_id": insight.get("id"),
            }
            creatives.append(creative)

    elif is_roas_issue:
        # ROAS problem - target campaigns with low ROAS but high spend
        low_roas_campaigns = sorted(
            [c for c in by_campaign if c.get("roas", 0) < roas_baseline * 0.8],
            key=lambda x: x.get("spend", 0),
            reverse=True
        )[:3]

        for campaign in low_roas_campaigns:
            camp_name = campaign.get("campaign", "Unknown")
            camp_roas = campaign.get("roas", 0.0)
            camp_spend = campaign.get("spend", 0.0)
            camp_revenue = campaign.get("revenue", 0.0)

            # Calculate ROAS gap
            roas_gap_pct = ((camp_roas - roas_baseline) / roas_baseline * 100) if roas_baseline > 0 else 0

            keywords = _extract_campaign_keywords(df, camp_name)
            keyword_str = ", ".join(keywords[:3]) if keywords else "value proposition"

            creative = {
                "campaign": camp_name,
                "issue_diagnosed": (
                    f"ROAS {roas_gap_pct:.1f}% below baseline "
                    f"({camp_roas:.2f}x vs {roas_baseline:.2f}x)"
                ),
                "evidence": {
                    "current_roas": round(camp_roas, 2),
                    "baseline_roas": round(roas_baseline, 2),
                    "delta_pct": round(roas_gap_pct, 2),
                    "campaign_spend": round(camp_spend, 2),
                    "campaign_revenue": round(camp_revenue, 2),
                },
                "recommendations": [
                    {
                        "headline": f"Optimize conversion messaging - focus on {keyword_str}",
                        "message": (
                            f"ROAS is {abs(roas_gap_pct):.1f}% below target "
                            f"({camp_roas:.2f}x vs {roas_baseline:.2f}x). "
                            f"Strengthen value proposition and add urgency with limited-time "
                            f"offers featuring {keyword_str}."
                        ),
                        "cta": "Shop Now - Limited Time",
                        "rationale": (
                            f"Campaign spent ${camp_spend:.0f} generating ${camp_revenue:.0f} revenue. "
                            "Conversion rate or average order value needs improvement."
                        ),
                    }
                ],
                "priority": impact,
                "linked_hypothesis_id": insight.get("id"),
            }
            creatives.append(creative)

    if not creatives:
        return None

    return {
        "insight_id": insight.get("id"),
        "hypothesis": hypothesis,
        "impact": impact,
        "confidence": insight.get("confidence", 0.0),
        "creatives": creatives,
    }


def generate_creatives(
    validated_insights: List[Dict[str, Any]],
    summary: Dict[str, Any],
    df: Any,
    *,
    base_dir: str = "logs/observability"
) -> List[Dict[str, Any]]:
    """
    Generate creative recommendations from validated insights.

    V2 Requirements Met:
    - Creatives reference specific diagnosed issues (CTR/ROAS deltas)
    - Evidence-backed (includes baseline, current, delta, spend)
    - Campaign-specific recommendations
    - Not generic - tied to actual performance data

    Args:
        validated_insights: List of validated hypotheses from evaluator
        summary: Data summary with campaign-level metrics
        df: Original DataFrame for keyword extraction
        base_dir: Directory for observability logs

    Returns:
        List of creative recommendation bundles
    """
    log_event(
        "creative_generator",
        "generate_started",
        {"num_insights": len(validated_insights)},
        base_dir=base_dir
    )

    output = []

    try:
        # Generate creatives for each validated insight
        for insight in validated_insights:
            try:
                creative_bundle = _generate_creative_from_insight(insight, summary, df)
                if creative_bundle:
                    output.append(creative_bundle)
            except Exception as e:
                log_event(
                    "creative_generator",
                    "creative_generation_error",
                    {
                        "insight_id": insight.get("id"),
                        "error": str(e)
                    },
                    base_dir=base_dir
                )

        # Validate creative output structure
        try:
            all_creatives = []
            for bundle in output:
                all_creatives.extend(bundle.get("creatives", []))

            if all_creatives:
                is_valid, errors = validate_creative_output(
                    all_creatives,
                    required_fields=["id", "creative_concept", "campaign", "issue_diagnosed"]
                )

                if not is_valid:
                    log_event(
                        "creative_generator",
                        "validation_warning",
                        {"errors": errors, "num_creatives": len(all_creatives)},
                        base_dir=base_dir
                    )

                    # Attempt to sanitize
                    for bundle in output:
                        if "creatives" in bundle:
                            bundle["creatives"] = sanitize_creative_output(
                                bundle["creatives"],
                                fix_missing_fields=True
                            )

                    log_event(
                        "creative_generator",
                        "output_sanitized",
                        {"num_bundles": len(output)},
                        base_dir=base_dir
                    )
        except Exception as e:
            log_event(
                "creative_generator",
                "validation_error",
                {"error": str(e)},
                base_dir=base_dir
            )

        # Log summary
        total_creatives = sum(len(bundle.get("creatives", [])) for bundle in output)
        log_event(
            "creative_generator",
            "generate_completed",
            {
                "num_bundles": len(output),
                "total_creatives": total_creatives,
            },
            base_dir=base_dir
        )

    except Exception as e:
        log_event(
            "creative_generator",
            "generate_failed",
            {"error": str(e)},
            base_dir=base_dir
        )
        raise

    return output


# Backward-compatible functions for tests
def find_low_ctr(summary: Dict, ctr_threshold: float = 0.01) -> List[Dict]:
    """Find campaigns with CTR below threshold (for test compatibility)."""
    return [c for c in summary.get("by_campaign", []) if c.get("ctr", 0) < ctr_threshold]
