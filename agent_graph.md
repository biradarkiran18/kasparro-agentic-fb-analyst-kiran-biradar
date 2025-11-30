# Agent Graph

This document documents the pipeline flow and the contracts between agents. It is intentionally concise and concrete: each step lists the inputs it expects, the outputs it produces, and the stable functions/files that implement it.

User Query → Planner → Data Agent → Insight Agent → Evaluator → Creative Generator → Report Builder

---

## Flow description and agent contracts

### 1) Planner
**Purpose:** convert a natural-language user query into a deterministic plan of steps the pipeline should run.

**Inputs**
- `query` (string) — free text from user.

**Outputs**
- `plan` (list of steps). Each step is a dict with:
  - `step`: string (e.g. `"load_data"`, `"summarize"`)
  - `description`: short explanation
  - `params`: optional dict of parameters

**Implementation**
- `src/agents/planner.py` — function `plan(query: str) -> dict`

**Notes**
- Planner should be idempotent and deterministic for the same query.

---

### 2) Data Agent
**Purpose:** load CSV, clean fields, compute base metrics and a schema fingerprint for drift detection.

**Inputs**
- `data_csv` path (from config)
- optional sample flags: `sample_mode`, `sample_size`, `chunksize`

**Outputs**
- `df` (pandas.DataFrame)
- `summary` (dict) with:
  - `global`: start/end dates, `total_spend`, `total_revenue`, `rows_in_input`, `daily_roas` (list of `{date, roas}`)
  - `by_campaign`: list of campaign dicts with `campaign_name, spend, impressions, clicks, purchases, revenue, ctr, roas`
- `schema_fingerprint` (written to `reports/schema_fingerprint.json`)

**Implementation**
- `src/agents/data_agent.py` — functions `load_data(...)`, `summarize(df)`

**Failure modes / checks**
- If missing numeric columns, `load_data` fills safe defaults and logs an observability event.
- If `chunksize` used, code must still produce deterministic samples when `sample_mode` is True.

---

### 3) Insight Agent
**Purpose:** generate structured hypotheses from the summary.

**Inputs**
- `summary` (from Data Agent)

**Outputs**
- `hyps` (list of dicts). Each hypothesis contains:
  - `id` (string)
  - `hypothesis` (string)
  - `rationale` (list of strings)
  - `evidence_from_summary` (list)
  - `initial_confidence` (float)

**Implementation**
- `src/agents/insight_agent.py` — function `generate_hypotheses(summary, confidence_min)`

**Notes**
- Hypotheses should include fields that evaluator expects (`initial_confidence`, optional `metrics_used`).

---

### 4) Evaluator
**Purpose:** validate hypotheses using deterministic rules and thresholds (CTR baseline, ROAS drop).

**Inputs**
- `hyps` (from Insight Agent)
- `summary`
- `thresholds` (static config values or dynamic thresholds computed from history)

**Outputs**
- `validated` (list): each entry:
  - `id`, `hypothesis`, `validated` (bool), `final_confidence` (float), `metrics_used`, `notes`
- `metrics` (dict): `num_hypotheses`, `num_validated`, `validation_rate`

**Implementation**
- `src/agents/evaluator.py` — function `validate(hyps, summary, thresholds)`
- Logs: validator should call `log_event("evaluator", "validate_started"... )` and `validate_completed` on finish.

**Failure modes / safeguards**
- If hypothesis fields missing (e.g., `initial_confidence` not float), evaluator must coerce safely and not raise.
- Do not flip a previously validated True → False due to another rule; prefer monotonic updates.

---

### 5) Creative Generator
**Purpose:** produce alternate creative text for low-CTR campaigns.

**Inputs**
- `low` (campaign list from summary filtered by CTR threshold)
- original `df`

**Outputs**
- `creatives` (list) written to `reports/creatives.json`

**Implementation**
- `src/agents/creative_generator.py` — functions `find_low_ctr(summary, ctr_threshold)` and `generate_creatives(low, df)`

---

### 6) Report Builder / Orchestrator
**Purpose:** coordinate agents, persist outputs, compute metrics and traces.

**Inputs**
- `query`, `config` (config has `data_csv`, thresholds defaults, observability dir)

**Outputs**
- `reports/insights.json`
- `reports/creatives.json`
- `reports/metrics.json` (fields below)
- `reports/schema_fingerprint.json`
- `logs/observability/*.json`

**Implementation**
- `src/orchestrator/orchestrator.py` — main entry `run(query) -> (validated, creatives)`

**Essential metrics (metrics.json)**
- `query`, `start_ts`, `run_ts`, `duration_ms`, `num_hypotheses`, `num_validated`, `validation_rate`, `num_creatives`, `rows_in_input`, `metrics_version`

---

## Minimal checks to validate readiness (run locally)

1. `PYTHONPATH="$(pwd)" pytest -q` — expect **all tests pass**.
2. `python run.py "Analyze ROAS drop in last 7 days"` — generates files in `reports/`.
3. `flake8 src tests --max-line-length=120` — no errors.

If any fail, fix failing unit tests first; tests assert precise contracts.

---

## Small, specific edits you should make now (copy/paste)

1. Replace existing `agent_graph.md` content with the block above. This makes the file explicit and reviewable.

2. Add these quick links inside `README.md` (under architecture) so reviewer can jump:
   ```markdown
   - Planner: src/agents/planner.py
   - Data Agent: src/agents/data_agent.py
   - Insight Agent: src/agents/insight_agent.py
   - Evaluator: src/agents/evaluator.py
   - Creative Generator: src/agents/creative_generator.py
   - Orchestrator: src/orchestrator/orchestrator.py
