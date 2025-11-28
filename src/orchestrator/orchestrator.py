import os
import uuid
import yaml
from datetime import datetime
from typing import Any, Dict, Tuple

from src.agents.creative_generator import find_low_ctr, generate_creatives
from src.agents.data_agent import load_data, summarize
from src.agents.evaluator import validate
from src.agents.insight_agent import generate_hypotheses
from src.utils.io_utils import write_json
from src.utils.observability import log_event, write_metrics, write_alert
from src.utils.retry_utils import apply_retry_logic, compute_extra_aggregates


def load_config(path: str = "config/config.yaml") -> Dict[str, Any]:
    with open(path) as f:
        return yaml.safe_load(f)


def _ts() -> str:
    return datetime.utcnow().isoformat() + "Z"


def run(query: str) -> Tuple[Any, Any]:
    cfg = load_config()
    obs_dir = cfg.get("observability_dir", "logs/observability")
    os.makedirs(obs_dir, exist_ok=True)

    correlation_id = str(uuid.uuid4())
    start_ts = _ts()
    trace_id = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    log_event("orchestrator", "run_started", {"query": query, "trace_id": trace_id,
              "correlation_id": correlation_id, "config": cfg}, base_dir=obs_dir)

    try:
        df = load_data(cfg["data_csv"], sample_mode=cfg.get("sample_mode", False),
                       sample_size=cfg.get("sample_size", 5000), chunksize=cfg.get("chunksize", None))
    except Exception as e:
        err = {"error": str(e)}
        log_event("orchestrator", "data_load_failed", {"error": err,
                  "correlation_id": correlation_id}, base_dir=obs_dir)
        write_alert({"level": "critical", "reason": "data_load_failed", "detail": str(e)})
        raise

    summary = summarize(df)
    log_event("data_agent", "summarize_complete", {"summary": {"start_date": summary.get(
        "global", {}).get("start_date")}, "correlation_id": correlation_id}, base_dir=obs_dir)

    try:
        hyps = generate_hypotheses(summary, cfg.get("confidence_min", 0.5))
    except Exception as e:
        log_event("insight_agent", "failed", {"error": str(e), "correlation_id": correlation_id}, base_dir=obs_dir)
        hyps = []

    thresholds = {
        "ctr_low_threshold": cfg.get("ctr_low_threshold", 0.01),
        "roas_drop_threshold": cfg.get("roas_drop_threshold", 0.2),
        "confidence_min": cfg.get("confidence_min", 0.5),
        "min_impressions": cfg.get("min_impressions", 100),
        "small_sample_spend": cfg.get("small_sample_spend", 10.0),
    }

    validated, eval_metrics = [], {}
    try:
        validated, eval_metrics = validate(hyps, summary, thresholds)
    except Exception as e:
        log_event("evaluator", "failed", {"error": str(e), "correlation_id": correlation_id}, base_dir=obs_dir)
        write_alert({"level": "warning", "reason": "evaluator_failed", "detail": str(e)})
        validated, eval_metrics = [], {}

    # retry/extra aggregates to improve confidence where needed
    try:
        extra = compute_extra_aggregates(df)
        validated = apply_retry_logic(validated, extra)
    except Exception:
        # don't break pipeline on observability extras
        pass

    low = find_low_ctr(summary, thresholds["ctr_low_threshold"])
    creatives = generate_creatives(low, df)

    os.makedirs("reports", exist_ok=True)
    write_json("reports/insights.json", validated)
    write_json("reports/creatives.json", creatives)

    trace_path = os.path.join(obs_dir, f"trace_orchestrator_{start_ts.replace(':','-')}_{correlation_id[:8]}.json")
    write_json(trace_path, {"timestamp": start_ts, "query": query, "insights": validated,
               "correlation_id": correlation_id, "trace_id": trace_id})

    metrics = {
        "query": query,
        "start_ts": start_ts,
        "run_ts": _ts(),
        "num_hypotheses": eval_metrics.get("num_hypotheses"),
        "num_validated": eval_metrics.get("num_validated"),
        "validation_rate": eval_metrics.get("validation_rate"),
        "num_creatives": len(creatives) if creatives else 0,
        "metrics_version": cfg.get("metrics_version", "v1"),
    }

    # compute duration (ms)
    try:
        fmt = "%Y-%m-%dT%H:%M:%S.%fZ"
        start_dt = datetime.strptime(start_ts, fmt)
        end_dt = datetime.strptime(metrics["run_ts"], fmt)
        metrics["duration_ms"] = int((end_dt - start_dt).total_seconds() * 1000)
    except Exception:
        metrics["duration_ms"] = None

    write_metrics(metrics, path=cfg.get("metrics_output", "reports/metrics.json"))

    with open("reports/report.md", "w", encoding="utf-8") as f:
        f.write("# Kasparro Agentic FB Analyst Report\n")
        f.write(f"Query: {query}\n")
        f.write(f"Run time: {_ts()}\n\n")
        f.write("Insights and creatives saved to reports/.\n")

    log_event("orchestrator", "run_completed", {"metrics": metrics,
              "trace_id": trace_id, "correlation_id": correlation_id}, base_dir=obs_dir)

    # anomaly alert: ROAS drop extreme
    try:
        if metrics.get("validation_rate", 0.0) < 0.01 and metrics.get("num_creatives", 0) == 0:
            write_alert({"level": "warning", "reason": "no_creatives_generated", "metrics": metrics})
        if metrics.get("validation_rate", 0.0) > 0.9:
            write_alert({"level": "info", "reason": "high_validation_rate", "metrics": metrics})
    except Exception:
        pass

    return validated, creatives
