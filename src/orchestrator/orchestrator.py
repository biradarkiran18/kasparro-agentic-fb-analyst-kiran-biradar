import yaml
import os
from datetime import datetime
from src.agents.data_agent import load_data, summarize
from src.agents.insight_agent import generate_hypotheses
from src.agents.evaluator import validate
from src.agents.creative_generator import find_low_ctr, generate_creatives
from src.utils.retry_utils import compute_extra_aggregates, apply_retry_logic
from src.utils.io_utils import write_json
from src.utils.observability import log_event, write_metrics


def load_config(path="config/config.yaml"):
    with open(path) as f:
        return yaml.safe_load(f)


def run(query):
    cfg = load_config()
    obs_dir = cfg.get("observability_dir", "logs/observability")
    os.makedirs(obs_dir, exist_ok=True)

    start_ts = datetime.utcnow().isoformat() + "Z"
    log_event(
        "orchestrator",
        "run_started",
        {"query": query, "config": cfg},
        base_dir=obs_dir,
    )

    df = load_data(cfg["data_csv"])
    summary = summarize(df)

    hyps = generate_hypotheses(summary, cfg.get("confidence_min"))

    thresholds = {
        "ctr_low_threshold": cfg.get("ctr_low_threshold", 0.01),
        "roas_drop_threshold": cfg.get("roas_drop_threshold", 0.2),
        "confidence_min": cfg.get("confidence_min", 0.5),
    }

    validated, eval_metrics = validate(hyps, summary, thresholds)

    extra = compute_extra_aggregates(df)
    validated = apply_retry_logic(validated, extra)

    low = find_low_ctr(summary, thresholds["ctr_low_threshold"])
    creatives = generate_creatives(low, df)

    os.makedirs("reports", exist_ok=True)
    write_json("reports/insights.json", validated)
    write_json("reports/creatives.json", creatives)

    trace_path = os.path.join(
        obs_dir, f"trace_orchestrator_{start_ts.replace(':','-')}.json"
    )
    write_json(
        trace_path,
        {"timestamp": start_ts, "query": query, "insights": validated},
    )

    metrics = {
        "query": query,
        "start_ts": start_ts,
        "run_ts": datetime.utcnow().isoformat() + "Z",
        "num_hypotheses": eval_metrics.get("num_hypotheses"),
        "num_validated": eval_metrics.get("num_validated"),
        "validation_rate": eval_metrics.get("validation_rate"),
        "num_creatives": len(creatives) if creatives else 0,
    }
    write_metrics(metrics, path=cfg.get("metrics_output", "reports/metrics.json"))

    with open("reports/report.md", "w") as f:
        f.write("# Kasparro Agentic FB Analyst Report\n")
        f.write(f"Query: {query}\n")
        f.write(f"Run time: {datetime.utcnow().isoformat()}Z\n\n")
        f.write("Insights and creatives saved to reports/.\n")

    log_event("orchestrator", "run_completed", {"metrics": metrics}, base_dir=obs_dir)

    # IMPORTANT: return only two values to satisfy existing tests
    return validated, creatives
