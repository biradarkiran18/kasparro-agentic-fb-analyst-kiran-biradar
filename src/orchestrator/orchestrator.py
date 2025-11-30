import yaml
import os
import uuid
from datetime import datetime
from typing import Any, Dict, Tuple

from src.agents.creative_generator import find_low_ctr, generate_creatives
from src.agents.data_agent import load_data, summarize
from src.agents.evaluator import validate
from src.agents.insight_agent import generate_hypotheses
from src.utils.io_utils import write_json
from src.utils.observability import log_event, write_metrics
from src.utils.schema import fingerprint_and_write, read_schema_fingerprint, detect_schema_drift
from src.utils.alerts import write_alert, alert_rule_roas_drop
from src.utils.retry_utils import apply_retry_logic, compute_extra_aggregates
from src.utils.thresholds import compute_dynamic_thresholds


def load_config(path: str = "config/config.yaml") -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
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

    log_event(
        "orchestrator",
        "run_started",
        {"query": query, "trace_id": trace_id, "correlation_id": correlation_id},
        base_dir=obs_dir,
    )

    # load data (support sample flags and chunksize via config)
    try:
        df = load_data(
            cfg["data_csv"],
            sample_mode=cfg.get("sample_mode", False),
            sample_size=cfg.get("sample_size", 5000),
            chunksize=cfg.get("chunksize", None),
        )
    except Exception as e:
        log_event(
            "orchestrator",
            "data_load_failed",
            {"error": str(e), "correlation_id": correlation_id},
            base_dir=obs_dir,
        )
        write_alert({"level": "critical", "reason": "data_load_failed", "detail": str(e)},
                    path=os.path.join(obs_dir, "alerts.json"))
        raise

    # write schema fingerprint and detect drift vs stored
    current_fp = fingerprint_and_write(df, "reports/schema_fingerprint.json")
    stored_fp = read_schema_fingerprint("reports/schema_fingerprint.json")
    drift = detect_schema_drift(current_fp, stored_fp)
    if drift.get("drift"):
        log_event("orchestrator", "schema_drift_detected", {"diff": drift.get("diff")}, base_dir=obs_dir)
        write_alert({"level": "warning", "reason": "schema_drift", "diff": drift.get("diff")},
                    path=os.path.join(obs_dir, "alerts.json"))

    log_event("data_agent", "summarize_start", {"rows": len(df)}, base_dir=obs_dir)
    summary = summarize(df)
    log_event("data_agent", "summarize_complete", {"start_date": summary.get(
        "global", {}).get("start_date"), "correlation_id": correlation_id}, base_dir=obs_dir)

    # compute dynamic thresholds with safe fallback to config defaults
    dyn: Dict[str, Any] = {}
    try:
        dyn = compute_dynamic_thresholds(
            df,
            window_days=cfg.get("window_days", 30),
            min_days=cfg.get("min_days", 7),
            ctr_z=cfg.get("ctr_z", 1.5),
            roas_z=cfg.get("roas_z", 1.0),
        )
    except Exception:
        dyn = {}

    thresholds: Dict[str, Any] = {
        "ctr_low_threshold": dyn.get("ctr_low_threshold", cfg.get("ctr_low_threshold", 0.01)),
        "roas_drop_threshold": dyn.get("roas_drop_threshold", cfg.get("roas_drop_threshold", 0.2)),
        "confidence_min": cfg.get("confidence_min", 0.5),
        "observability_dir": obs_dir,
    }

    # insight agent
    try:
        hyps = generate_hypotheses(summary, cfg.get("confidence_min", 0.5))
    except Exception as e:
        log_event("insight_agent", "generate_failed", {"error": str(
            e), "correlation_id": correlation_id}, base_dir=obs_dir)
        hyps = []

    # evaluator
    try:
        validated, eval_metrics = validate(hyps, summary, thresholds)
    except Exception as e:
        log_event("evaluator", "validate_failed", {"error": str(e), "correlation_id": correlation_id}, base_dir=obs_dir)
        write_alert({"level": "warning", "reason": "evaluator_failed", "detail": str(e)},
                    path=os.path.join(obs_dir, "alerts.json"))
        validated, eval_metrics = [], {"num_hypotheses": 0, "num_validated": 0, "validation_rate": 0.0}

    # retry extras (non-fatal)
    try:
        extra = compute_extra_aggregates(df)
        validated = apply_retry_logic(validated, extra)
    except Exception:
        log_event("observability", "extra_aggregates_failed", {"correlation_id": correlation_id}, base_dir=obs_dir)

    # creatives
    low = find_low_ctr(summary, thresholds["ctr_low_threshold"])
    creatives = generate_creatives(low, df)

    # write outputs
    os.makedirs("reports", exist_ok=True)
    write_json("reports/insights.json", validated)
    write_json("reports/creatives.json", creatives)

    trace_path = os.path.join(obs_dir, f"trace_orchestrator_{start_ts.replace(':','-')}_{correlation_id[:8]}.json")
    write_json(trace_path, {"timestamp": start_ts, "query": query,
               "insights": validated, "trace_id": trace_id, "dyn_thresholds": dyn})

    # metrics
    metrics = {
        "query": query,
        "start_ts": start_ts,
        "run_ts": _ts(),
        "num_hypotheses": eval_metrics.get("num_hypotheses") if isinstance(eval_metrics, dict) else None,
        "num_validated": eval_metrics.get("num_validated") if isinstance(eval_metrics, dict) else None,
        "validation_rate": eval_metrics.get("validation_rate") if isinstance(eval_metrics, dict) else None,
        "num_creatives": len(creatives) if creatives else 0,
        "rows_in_input": int(summary.get("global", {}).get("rows_in_input", 0)),
        "metrics_version": cfg.get("metrics_version", "v1"),
        # put most important dyn thresholds into metrics for downstream alerting
        "dyn_ctr_low_threshold": dyn.get("ctr_low_threshold"),
        "dyn_roas_drop_threshold": dyn.get("roas_drop_threshold"),
    }

    # add roas_drop to metrics if available (evaluator may attach it)
    if isinstance(eval_metrics, dict) and "roas_drop" in eval_metrics:
        metrics["roas_drop"] = eval_metrics["roas_drop"]

    # compute duration
    try:
        fmt = "%Y-%m-%dT%H:%M:%S.%fZ"
        start_dt = datetime.strptime(start_ts, fmt)
        end_dt = datetime.strptime(metrics["run_ts"], fmt)
        metrics["duration_ms"] = int((end_dt - start_dt).total_seconds() * 1000)
    except Exception:
        metrics["duration_ms"] = None

    write_metrics(metrics, path=cfg.get("metrics_output", "reports/metrics.json"))

    # advanced alert rules (example: roas drop + low validation/no creatives)
    alert_result = alert_rule_roas_drop(metrics, thresholds)
    if alert_result.get("alerted"):
        write_alert({"level": "warning", "reason": alert_result.get("reason"),
                    "metrics": metrics}, path=os.path.join(obs_dir, "alerts.json"))
        log_event("orchestrator", "alert_raised", {"reason": alert_result.get("reason")}, base_dir=obs_dir)

    # human report
    with open("reports/report.md", "w", encoding="utf-8") as f:
        f.write("# Agentic FB Analyst Report\n")
        f.write(f"Query: {query}\n")
        f.write(f"Run time: {_ts()}\n\n")
        f.write("Insights and creatives saved to reports/.\n")

    log_event("orchestrator", "run_completed", {"metrics": metrics,
              "trace_id": trace_id, "correlation_id": correlation_id}, base_dir=obs_dir)

    return validated, creatives
