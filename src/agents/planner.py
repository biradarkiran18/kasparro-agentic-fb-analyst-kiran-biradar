def plan(query: str):
    return {
        "query": query,
        "steps": [
            "load_data",
            "summarize_data",
            "generate_insights",
            "validate_insights",
            "identify_low_ctr",
            "generate_creatives",
            "produce_report"
        ]
    }
