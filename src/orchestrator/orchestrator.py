import yaml, os
from datetime import datetime
from src.agents.planner import plan
from src.agents.data_agent import load_data, summarize
from src.agents.insight_agent import generate_hypotheses
from src.agents.evaluator import validate
from src.agents.creative_generator import find_low_ctr, generate_creatives
from src.utils.retry_utils import compute_extra_aggregates, apply_retry_logic
from src.utils.io_utils import write_json

def load_config(path="config/config.yaml"):
    with open(path) as f:
        return yaml.safe_load(f)

def run(query):
    cfg = load_config()

    df = load_data(cfg["data_csv"])
    plan_out = plan(query)

    summary = summarize(df)

    hyps = generate_hypotheses(summary, cfg["confidence_min"])

    validated = validate(hyps, summary, cfg)

    extra = compute_extra_aggregates(df)
    validated = apply_retry_logic(validated, extra)

    low = find_low_ctr(summary, cfg["ctr_low_threshold"])
    creatives = generate_creatives(low, df)

    os.makedirs("reports", exist_ok=True)
    os.makedirs("reports/observability", exist_ok=True)

    write_json("reports/insights.json", validated)
    write_json("reports/creatives.json", creatives)

    write_json("reports/observability/trace_example.json", {
        "timestamp": str(datetime.now()),
        "query": query,
        "insights": validated
    })

    with open("reports/report.md", "w") as f:
        f.write("# Kasparro Agentic FB Analyst Report\n")
        f.write(f"Query: {query}\n")
        f.write(f"Run time: {datetime.now()}\n\n")
        f.write("Insights and creatives saved to reports/.\n")

    return validated, creatives
