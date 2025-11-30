from typing import Dict, Any


def plan(query: str) -> Dict[str, Any]:
    # explicit, traceable steps (7 steps as tests expect)
    steps = [
        {"step": "load_data", "description": "load CSV and basic pre-processing"},
        {"step": "summarize", "description": "compute global and per-campaign aggregates"},
        {"step": "generate_hypotheses", "description": "produce hypotheses from summary"},
        {"step": "validate", "description": "validate hypotheses against thresholds"},
        {"step": "compute_extra_aggregates", "description": "compute extra aggregates for retries"},
        {"step": "generate_creatives", "description": "produce creative recommendations"},
        {"step": "write_reports", "description": "persist outputs and observability traces"},
    ]
    return {"query": query, "steps": steps}
