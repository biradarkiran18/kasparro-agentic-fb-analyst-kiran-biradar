# src/orchestrator/orchestrator.py

from __future__ import annotations

import traceback
from typing import Any, Dict, Optional

from src.utils.io_utils import load_csv
from src.utils.schema import (
    schema_fingerprint_from_df,
    read_schema_fingerprint,
    detect_schema_drift,
    fingerprint_and_write,
    validate_schema,
    SchemaValidationError,
)
from src.utils.observability import log_event, write_json_report
from src.utils.baseline import (
    compute_global_baselines,
    evidence_from_summary_and_baseline,
)
from src.utils.thresholds import compute_dynamic_thresholds

from src.agents.planner import plan
from src.agents.data_agent import summarize_data
from src.agents.insight_agent import generate_hypotheses
from src.agents.evaluator import validate
from src.agents.creative_generator import generate_creatives


def _safe(df: Any) -> Any:
    """Simple helper to allow None-passing."""
    return df if df is not None else {}


def run(
    input_path: str = "data/sample_fb_ads.csv",
    config: Optional[Dict[str, Any]] = None,
    base_dir: str = "logs/observability",
) -> Dict[str, Any]:
    """
    Full end-to-end V2 orchestrator:
      1. Load data
      2. Schema fingerprint + drift detection
      3. Planner → tasks
      4. Data Agent → summary
      5. Compute baselines + thresholds
      6. Insight Agent → hypotheses
      7. Evaluator → validated hypotheses (with evidence)
      8. Creative Generator → creatives linked to hypotheses
      9. Write all reports + observability

    Returns a dict containing all outputs so tests and user-facing environments
    can import and re-use.
    """

    cfg = config or {}
    log_event("orchestrator", "run_started", {"input": input_path}, base_dir=base_dir)

    try:
        # ------------------------------------------------------------
        # 1) LOAD INPUT DATA (with optional chunking for large files)
        # ------------------------------------------------------------
        chunksize = cfg.get("chunksize", None)
        if chunksize:
            log_event("orchestrator", "loading_with_chunking", {"chunksize": chunksize}, base_dir=base_dir)

        df = load_csv(input_path, chunksize=chunksize)
        if df is None:
            raise ValueError(f"Failed to load DataFrame from {input_path}")

        log_event("orchestrator", "data_loaded", {"rows": len(df), "columns": len(df.columns)}, base_dir=base_dir)

        # ------------------------------------------------------------
        # 2) SCHEMA VALIDATION (PRE-RUN)
        # ------------------------------------------------------------
        log_event("orchestrator", "schema_validation_started", {}, base_dir=base_dir)
        try:
            is_valid, schema_errors = validate_schema(df, strict=False)
            if not is_valid:
                log_event(
                    "orchestrator",
                    "schema_validation_failed",
                    {"errors": schema_errors},
                    base_dir=base_dir
                )
                # Raise error with clear message
                raise SchemaValidationError(
                    "Data schema validation failed:\n" +
                    "\n".join(f"  - {e}" for e in schema_errors)
                )
            log_event("orchestrator", "schema_validation_passed", {}, base_dir=base_dir)
        except SchemaValidationError:
            raise
        except Exception as e:
            log_event("orchestrator", "schema_validation_error", {"error": str(e)}, base_dir=base_dir)
            # Continue with warning
            pass

        # ------------------------------------------------------------
        # 3) SCHEMA FINGERPRINTING & DRIFT DETECTION
        # ------------------------------------------------------------
        new_fp = schema_fingerprint_from_df(df)
        old_fp = read_schema_fingerprint("reports/schema_fingerprint.json") or {}

        drift_report = detect_schema_drift(old_fp, new_fp) if old_fp else {"drift": False, "diff": {}}
        fingerprint_and_write(df, "reports/schema_fingerprint.json")

        # ------------------------------------------------------------
        # 4) PLANNER
        # ------------------------------------------------------------
        tasks = plan(cfg)

        # ------------------------------------------------------------
        # 5) DATA AGENT — SUMMARY STATISTICS
        # ------------------------------------------------------------
        summary = summarize_data(df, cfg)

        # ------------------------------------------------------------
        # 6) BASELINES + DYNAMIC THRESHOLDS
        # ------------------------------------------------------------
        global_baseline = compute_global_baselines(df)
        dyn_thresholds = compute_dynamic_thresholds(df)
        cfg.update(dyn_thresholds)
        cfg["roas_baseline"] = global_baseline  # Pass baseline to insight agent

        evidence_baseline = evidence_from_summary_and_baseline(summary, global_baseline)

        # ------------------------------------------------------------
        # 7) INSIGHT AGENT — HYPOTHESES
        # ------------------------------------------------------------
        hypotheses = generate_hypotheses(summary, tasks, cfg)

        # ------------------------------------------------------------
        # 8) EVALUATOR — VALIDATION + EVIDENCE
        # ------------------------------------------------------------
        validated, val_metrics = validate(
            hypotheses,
            summary,
            cfg,
            df=df,
            base_dir=base_dir,
        )

        # ------------------------------------------------------------
        # 8) CREATIVE GENERATOR — evidence-linked creatives
        # ------------------------------------------------------------
        creatives = generate_creatives(
            validated,
            summary,
            df,
            base_dir=base_dir
        )

        # ------------------------------------------------------------
        # 9) WRITE ALL REPORTS
        # ------------------------------------------------------------
        write_json_report("reports/insights.json", validated)
        write_json_report("reports/creatives.json", creatives)
        write_json_report("reports/metrics.json", val_metrics)
        write_json_report("reports/drift_report.json", drift_report)
        write_json_report("reports/baseline_summary.json", global_baseline)
        write_json_report("reports/evidence_baseline.json", evidence_baseline)

        log_event(
            "orchestrator",
            "run_completed",
            {"metrics": val_metrics, "drift": drift_report},
            base_dir=base_dir,
        )

        return {
            "summary": summary,
            "hypotheses": hypotheses,
            "validated": validated,
            "creatives": creatives,
            "metrics": val_metrics,
            "drift": drift_report,
            "baseline": global_baseline,
            "evidence": evidence_baseline,
        }

    except Exception as e:
        tb = traceback.format_exc()
        log_event(
            "orchestrator",
            "run_failed",
            {"error": str(e), "traceback": tb},
            base_dir=base_dir,
        )
        raise
