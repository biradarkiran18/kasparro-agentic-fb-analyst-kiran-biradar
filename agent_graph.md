# How The Agents Work (v2.0)

This doc explains what each agent does, what it needs as input, what it produces, and how it handles problems.

**Pipeline Flow:**
```
Your Question → Planner → Data Agent → Baseline Computer → Insight Agent → Evaluator → Creative Generator → Final Reports
                                  ↓
                        Schema validation & drift detection
                                  ↓
                        Observability logs (for debugging)
```

---

## Design Principles

- **Evidence-based**: Every insight cites specific numbers (CTR delta %, ROAS delta %, baseline values)
- **Validated**: Evaluator ranks hypotheses by severity (critical/high/medium/low)
- **Observable**: Each agent logs decisions with reasons
- **Schema governance**: Checks data quality before processing, tracks changes
- **Error-resilient**: Handles NaN, infinity, missing columns, empty data gracefully
- **LLM-safe**: Validates AI outputs, retries failures, fixes malformed JSON
- **Scalable**: Loads huge CSVs in chunks to avoid memory issues

---

## The Agents

### 1) Planner

**What it does:** Turns your question into a concrete execution plan.

**Input:**
- `query` (string) — Your question (e.g., "Why did ROAS drop last week?")

**Output:**
- `plan` (dict):
  - `steps`: What to do, in order
  - `window_days`: Time range from your question (defaults to 7 if unclear)
  - `focus_metric`: Main metric to analyze (e.g., "roas", "ctr")

**Code:** `src/agents/planner.py` → `plan(query)`

**Logs:** When it starts/finishes, how it interpreted your question

**Edge cases:**
- Vague questions: Uses 7-day window and "roas" metric as defaults
- No time reference: Analyzes all available data

---

### 2) Data Agent

**What it does:** Loads CSV, validates schema, computes summary stats.

**Input:**
- `data_csv`: Path to your CSV
- `chunksize` (optional): Batch size for huge files
- `sample_mode` (optional): Whether to sample for testing
- `sample_size` (optional): Number of rows if sampling

**Output:**
- `df`: Your data, cleaned
- `summary`:
  - `global`: Date range, total spend/revenue, rows processed, daily ROAS timeline
  - `by_campaign`: Stats per campaign (spend, impressions, clicks, purchases, revenue, CTR, ROAS)
- `schema_fingerprint`: Written to `reports/schema_fingerprint.json`

**Code:**
- `src/agents/data_agent.py`:
  - `load_csv_safe()`: Handles chunked loading
  - `load_and_summarize()`: Combined load + summarize
  - `summarize()`: Computes metrics
- `src/utils/io_utils.py` → `load_csv()`: Basic CSV loading

**Schema validation:**
- Checks for required columns before processing
- Required: `campaign_name`, `date`, `spend`, `impressions`, `clicks`, `purchases`, `revenue`
- Converts types correctly (numbers → float64, dates → datetime)
- Missing columns: Raises error with clear message

**Schema drift detection:**
- Compares current schema to baseline
- Detects: columns added/removed, type changes, big row count differences
- Writes findings to `reports/drift_report.json`

**Error handling:**
- Empty CSV: Returns empty DataFrame, warns you
- Missing columns: Fills with 0.0, logs alert
- NaN or infinity: Replaces with 0.0, logs what changed
- Malformed CSV: Skips bad lines, logs count
- Chunked loading fails: Falls back to regular loading

**Logs:** Load progress (every 10th chunk), schema validation results, data quality issues

**Performance:** Handles 1M+ rows in ~300MB chunks, small overhead (~10%) for large files

---

### 3) Baseline Computer

**What it does:** Calculates historical percentile thresholds for CTR and ROAS.

**Input:**
- `summary`: From Data Agent (needs `daily_roas` field)
- `window_days`: Time range for baseline (default: 7)

**Output:**
- `baseline`:
  - `ctr_baseline`: 50th percentile of campaign CTRs
  - `roas_baseline`: 50th percentile of daily ROAS
  - `ctr_threshold`: 10th percentile (low-CTR cutoff)
  - `roas_drop_threshold`: 25th percentile (ROAS drop cutoff)
  - `computed_from_days`: Actual days used
  - `campaigns_analyzed`: Number of campaigns

**Code:** `src/agents/baseline.py` → `compute_global_baseline()`

**Why percentiles instead of fixed numbers?**
- Adapts to your campaign patterns (seasonality, budget changes)
- Robust against outliers (10th/25th/50th percentiles resist contamination)
- Evidence-based (derived from your actual data distribution)

**Logs:** Percentile values, campaigns included, time range

**Edge cases:**
- < 7 days of data: Uses all available, logs warning
- Empty campaigns: Returns 0.0 baseline, logs alert
- Single campaign: Percentiles collapse to single value

---

### 4) Insight Agent

**What it does:** Generates hypotheses backed by evidence.

**Input:**
- `summary`: Global + campaign metrics
- `baseline`: Historical thresholds
- `confidence_min`: Minimum confidence to include (default: 0.3)

**Output:**
- `hyps` (list):
  - `id`: Unique identifier
  - `hypothesis`: Natural language statement
  - `rationale`: Evidence-based reasoning (list)
  - `evidence_from_summary`: Specific metrics referenced (list)
  - `initial_confidence`: 0.0-1.0 score
  - `metrics_used`: Campaign/metric combinations (list)

**Code:**
- `src/agents/insight_agent.py` → `generate_hypotheses()`
- `src/utils/llm_validation.py`:
  - `validate_hypothesis_output()`: Checks required fields, confidence range
  - `sanitize_hypothesis_output()`: Clamps confidence, adds missing fields
  - `retry_with_backoff()`: Exponential backoff (1s, 2s, 4s)

**LLM validation:**
- Required fields: `id`, `hypothesis`, `rationale`, `initial_confidence`
- Confidence must be float in [0.0, 1.0]
- Rationale must be non-empty list
- Malformed JSON: Repairs (trailing commas, missing brackets), retries (3 attempts)
- Sanitization: Clamps confidence, adds empty defaults for missing fields

**Logs:** Generation start/end, LLM calls, validation pass/fail, sanitization actions

**Edge cases:**
- LLM returns non-JSON: Repair → retry → sanitization fallback
- Confidence > 1.0: Clamped to 1.0, logged
- Missing rationale: Empty list substituted, logged

---

### 5) Evaluator

**What it does:** Validates hypotheses and ranks severity.

**Input:**
- `hyps`: From Insight Agent
- `summary`: Campaign metrics
- `baseline`: Thresholds
- `thresholds`: Severity levels from config

**Output:**
- `validated` (list):
  - `id`, `hypothesis`, `validated` (bool), `final_confidence` (float)
  - `severity`: critical/high/medium/low/none
  - `metrics_used`: Evidence metrics (list)
  - `notes`: Validation reasoning (string)
  - `delta_pct` (optional): % change from baseline
- `metrics`: `num_hypotheses`, `num_validated`, `validation_rate`

**Code:** `src/agents/evaluator.py` → `validate()`

**Severity rules** (from `config.yaml`):
- **Critical**: delta < -50% OR confidence > 0.8 with delta < -30%
- **High**: delta < -30% OR confidence > 0.7 with delta < -20%
- **Medium**: delta < -20% OR confidence > 0.5 with delta < -10%
- **Low**: delta < -10% OR confidence > 0.4
- **None**: No criteria met

**Confidence adjustments:**
- CTR below threshold: +0.2
- ROAS drop detected: +0.3
- Both conditions: +0.5 (capped at 1.0)

**Logs:** Validation start/end, hypothesis validated/rejected, severity reasoning

**Edge cases:**
- Missing confidence: Defaults to 0.5, logs warning
- Baseline = 0: Skips delta calculation, uses absolute thresholds
- Empty hypotheses: Returns empty validated list, logs info

---

### 6) Creative Generator

**What it does:** Creates campaign-specific recommendations.

**Input:**
- `validated`: From Evaluator
- `summary`: Campaign metrics
- `ctr_threshold`: From baseline

**Output:**
- `creatives` (list):
  - `campaign_name`: Campaign name (string)
  - `current_ctr`: Actual CTR (float)
  - `ctr_baseline`: Historical baseline (float)
  - `creative_bundle`:
    - `headline`: Headline text (string)
    - `body`: Body text (string)
    - `cta`: Call-to-action (string)
    - `targeting_suggestions`: Targeting ideas (list)

**Code:**
- `src/agents/creative_generator.py`:
  - `find_low_ctr()`: Identifies underperforming campaigns
  - `generate_creatives()`: Creates recommendations
- `src/utils/llm_validation.py`:
  - `validate_creative_output()`: Checks required fields
  - `sanitize_creative_output()`: Adds defaults for missing fields

**LLM validation:**
- Required fields: `headline`, `body`, `cta`
- All must be non-empty strings
- Sanitization: Adds "Missing [field]" placeholders
- Retry: 3 attempts with exponential backoff

**Logs:** Low-CTR identification, generation start/end, validation results

**Edge cases:**
- No low-CTR campaigns: Returns empty list, logs info
- LLM returns partial creative: Sanitization adds defaults, logs warning
- Validation fails after retries: Uses sanitized fallback, logs alert

---

### 7) Orchestrator

**What it does:** Coordinates everything, writes reports, captures metrics.

**Input:**
- `query`: Your question (string)
- `config`: Settings from `config/config.yaml`

**Output (files written):**
- `reports/insights.json`: Validated hypotheses
- `reports/creatives.json`: Recommendations
- `reports/metrics.json`: Pipeline stats
- `reports/schema_fingerprint.json`: Schema snapshot
- `reports/drift_report.json`: Schema drift findings
- `logs/observability/*.json`: Per-agent logs

**Code:** `src/orchestrator/orchestrator.py` → `run(query)`

**Pipeline metrics** (`reports/metrics.json`):
- `query`, `start_ts`, `run_ts`, `duration_ms`
- `num_hypotheses`, `num_validated`, `validation_rate` (%)
- `num_creatives`, `rows_in_input`, `metrics_version`

**Error handling:**
- Agent failures: Catches exceptions, logs context, continues with partial results
- Missing config: Uses safe defaults, logs warnings
- I/O errors: Retries writes (3 attempts), logs failures

**Logs:** Per-agent execution, decision rationale, alerts

**Edge cases:**
- Agent raises exception: Logs error, returns empty results, continues pipeline
- Config missing: Uses hardcoded defaults, logs warning
- Output directory missing: Creates recursively, logs info

---

## Testing Strategy (49 Tests)

### Core tests (12)
- Planner, Data Agent, Insight Agent, Evaluator, Creative Generator
- Orchestrator (end-to-end)
- Schema validation and drift detection
- Alerts and thresholds

### Edge cases (30 in `test_edge_cases.py`)
- Empty data, NaN handling, missing columns
- Zero division (0 impressions, 0 spend)
- Malformed CSV, extreme values (Inf, -Inf, huge numbers)
- Evaluator edge cases (empty hypotheses, missing confidence, baseline=0)
- Baseline edge cases (single day, single campaign, no ROAS data)

### LLM validation (19 in `test_llm_validation.py`)
- Hypothesis and creative validation
- JSON repair (trailing commas, missing brackets, quote issues)
- Retry mechanism (transient failures, exponential backoff, max retries)
- Sanitization (confidence clamping, field defaults, edge cases)

---

## Key Files

**Agents:**
- `src/agents/planner.py` — Query → Plan
- `src/agents/data_agent.py` — CSV → DataFrame + Summary
- `src/agents/baseline.py` — Summary → Dynamic Thresholds
- `src/agents/insight_agent.py` — Summary + Baseline → Hypotheses
- `src/agents/evaluator.py` — Hypotheses → Validated Insights
- `src/agents/creative_generator.py` — Validated Insights → Recommendations

**Utilities:**
- `src/utils/llm_validation.py` — LLM output validation, retry, sanitization
- `src/utils/schema.py` — Schema validation, drift detection
- `src/utils/io_utils.py` — CSV/JSON I/O, chunked loading
- `src/utils/observability.py` — Logging

**Config:**
- `config/config.yaml` — Thresholds, severity levels, file paths

**Tests:**
- `tests/test_edge_cases.py` — 30 edge case tests
- `tests/test_llm_validation.py` — 19 LLM validation tests
- `tests/test_*.py` — 12 core agent tests

---

## V2 Improvements

**Evidence-based:**
- Every insight references specific metrics (CTR delta %, ROAS delta %)
- Baseline comparison using historical percentiles
- Delta calculations: `(current - baseline) / baseline * 100`

**Validation:**
- Severity classification (critical/high/medium/low/none)
- Confidence adjustments based on evidence strength
- LLM output validation with retry and sanitization

**Error handling:**
- 30 edge case tests (malformed data, NaN/Inf, missing columns)
- Comprehensive try/except blocks with structured logging
- Graceful degradation (sanitization fallbacks, partial results)

**Schema governance:**
- Pre-run validation with explicit schema definition
- Drift detection comparing current vs baseline
- Schema versioning and timestamping

**Observability:**
- Per-agent decision logs with structured JSON
- Alert rules for data quality, validation rates, schema drift
- Input/output summaries, error context logging

**Scalability:**
- Chunked CSV loading for multi-GB files
- Progress logging every 10 chunks
- Memory-efficient concatenation

**Developer experience:**
- 49 comprehensive tests (12 core + 30 edge cases + 19 LLM validation)
- Clear agent contracts documented
- Makefile commands: `make setup`, `make test`, `make run`
