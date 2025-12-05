# Facebook Ads Analytics Pipeline (v2.0)

**By Kiran Biradar**

[![Python](https://img.shields.io/badge/python-3.11-blue.svg)]()
[![Tests](https://img.shields.io/badge/tests-49%20passing-brightgreen.svg)]()
[![Status](https://img.shields.io/badge/build-production--ready-green.svg)]()

An automated system that analyzes Facebook Ads data to find performance problems and suggest fixes. Every insight is backed by real numbers from your data, not generic advice.

## What Makes This Production-Ready

Version 2.0 isn't just about working code—it's about code that handles real-world messiness:

### Actual Evidence, Not Generic Tips

Every insight references real numbers from your campaigns:
- "CTR dropped 32% vs your baseline" (not just "CTR is low")
- Baselines computed from your historical data, not arbitrary thresholds
- Issues ranked by severity (critical/high/medium/low) based on actual impact
- Recommendations tied to specific campaigns with their spend and revenue

### Smart Validation

The system doesn't just generate insights—it validates them:
- Each hypothesis includes concrete evidence: `{hypothesis, evidence: {ctr_delta: -32%}, impact: "high", confidence: 0.74}`
- Baselines adapt to your data patterns (using percentiles, not fixed numbers)
- Confidence scores reflect how strong the evidence is
- LLM outputs get validated and fixed automatically if malformed
- Missing or weird values get sanitized instead of crashing the pipeline

### Handles Real-World Data Problems

Your CSV has missing columns? NaN values? Infinity in the math? This handles it:
- Gracefully deals with missing or renamed columns
- Protects against NaN and infinity in calculations
- Warns you about empty data instead of silently failing
- Logs errors with full context so you can actually debug them
- 30+ edge case tests covering all the weird stuff that breaks most scripts

### Data Quality Checks

Before running analysis, the system checks your data:
- Validates that your CSV has the expected columns
- Detects when your schema changes (columns added/removed/renamed)
- Tracks data structure over time with fingerprints
- Everything configurable in `config.yaml`—no magic numbers buried in code

### Actually Useful Logs

Logs that help you understand what happened and why:
- Each agent logs what it's doing and why it made each decision
- Input/output summaries show data flowing through the pipeline
- Errors include full context for debugging
- Timestamped folders keep runs organized
- Another engineer (or you in 3 months) can figure out what happened

### Works with Large Files

Got a 5GB CSV? No problem:
- Loads data in chunks to avoid memory errors
- Configurable batch size via `chunksize` parameter
- Progress logging so you know it's not frozen

### Easy to Work With

- Installation that works on the first try
- Makefile commands: `make setup`, `make run`, `make test`
- Docs explaining how the system works and how to extend it
- 49 tests covering normal cases and weird edge cases

### Recommendations That Make Sense

Creative suggestions tied to actual problems:
- "Your CTR is 32% below baseline (0.0123 vs 0.0181)"
- Recommendations include the specific metrics that triggered them
- Targeted to individual campaigns with their spend/revenue context
- Not generic advice—each suggestion addresses a real issue in your data

---

## How It Works

This is a multi-agent pipeline where each agent has one job:

```
┌─────────────┐
│   Planner   │ → Figures out what analysis to run
│             │    (extracts time windows, metrics from your query)
└──────┬──────┘
       ↓
┌─────────────┐
│ Data Agent  │ → Loads your CSV and computes summary stats
│             │    (handles missing columns, weird values)
└──────┬──────┘
       ↓
┌─────────────┐
│  Baseline   │ → Calculates historical CTR/ROAS baselines
│  Computer   │    (uses percentiles for robustness)
└──────┬──────┘
       ↓
┌─────────────┐
│Insight Agent│ → Generates hypotheses backed by evidence
│             │    (each one includes the deltas and confidence)
└──────┬──────┘
       ↓
┌─────────────┐
│  Evaluator  │ → Validates insights and scores severity
│             │    (filters out weak hypotheses)
└──────┬──────┘
       ↓
┌─────────────┐
│  Creative   │ → Generates campaign-specific recommendations
│  Generator  │    (tied to validated insights)
└─────────────┘
```

The Orchestrator coordinates everything and writes the reports.

### Design Philosophy

1. **Evidence first** – Every insight must show its work with numbers
2. **Fail gracefully** – Log problems and keep going instead of crashing
3. **Explain decisions** – Logs show why each choice was made
4. **Everything configurable** – Thresholds live in `config.yaml`, not buried in code
5. **Test the weird stuff** – Unit tests for edge cases, not just happy paths

---

## Project Structure

```
kasparro-agentic-fb-analyst-kiran-biradar/
│
├── config/
│   └── config.yaml                    # All thresholds and settings
│
├── data/
│   └── sample_fb_ads.csv              # Sample dataset
│
├── logs/
│   └── observability/                 # Per-agent execution logs
│       ├── orchestrator_run_*.json
│       ├── data_agent_*.json
│       ├── insight_agent_*.json
│       └── alerts.json
│
├── prompts/
│   ├── planner.md
│   ├── data_agent.md
│   ├── insight_agent.md
│   ├── evaluator.md
│   └── creative_generator.md
│
├── reports/
│   ├── insights.json                  # Validated hypotheses
│   ├── creatives.json                 # Recommendations
│   ├── metrics.json                   # Pipeline stats
│   ├── schema_fingerprint.json        # Schema tracking
│   └── drift_report.json              # Schema changes
│
├── src/
│   ├── agents/
│   │   ├── planner.py
│   │   ├── data_agent.py
│   │   ├── insight_agent.py
│   │   ├── evaluator.py
│   │   └── creative_generator.py
│   │
│   ├── orchestrator/
│   │   └── orchestrator.py            # Main coordinator
│   │
│   └── utils/
│       ├── io_utils.py                # CSV/JSON I/O
│       ├── observability.py           # Logging
│       ├── llm_validation.py          # LLM output validation
│       ├── schema.py                  # Schema validation
│       └── thresholds.py              # Dynamic thresholds
│
├── tests/
│   ├── test_planner.py
│   ├── test_data_agent.py
│   ├── test_insight_agent.py
│   ├── test_evaluator.py
│   ├── test_creative_generator.py
│   ├── test_orchestrator.py
│   ├── test_edge_cases.py             # 30 edge case tests
│   ├── test_llm_validation.py         # 19 LLM validation tests
│   ├── test_schema.py
│   ├── test_thresholds.py
│   └── test_alerts.py
│
├── Makefile                            # Build commands
├── pytest.ini                          # Test configuration
├── run.py                              # Main entry point
├── requirements.txt                    # Dependencies
├── README.md                           # This file
├── agent_graph.md                      # Agent architecture docs
├── EVAL_CHECKLIST.md                  # Feature checklist
└── PR_SELF_REVIEW.md                  # Design decisions
```

---

## Getting Started

### What You Need
- Python 3.11 or newer
- Conda (recommended) or virtualenv

### Installation

```bash
# Clone this repo
git clone https://github.com/biradarkiran18/kasparro-agentic-fb-analyst-kiran-biradar.git
cd kasparro-agentic-fb-analyst-kiran-biradar

# Set up Python environment
conda create -n kasparro python=3.11 -y
conda activate kasparro

# Install everything
pip install -r requirements.txt
```

### Running It

Easiest way:
```bash
python run.py
```

Or use the Makefile:
```bash
make setup   # Install dependencies
make run     # Run the pipeline
make test    # Run all 49 tests
```

### What You Get

After it runs, check these files:
- `reports/insights.json` - Problems found with evidence
- `reports/creatives.json` - Specific recommendations per campaign
- `reports/metrics.json` - Pipeline stats and validation rates
- `logs/observability/` - Detailed logs of what each agent did

---

## Understanding The Output

### Insights Format

Each insight shows you exactly what's wrong:

```json
{
  "id": "abc123",
  "hypothesis": "CTR has dropped by 32% vs baseline — possible creative fatigue",
  "impact": "high",
  "confidence": 0.74,
  "passed": true,
  "evidence": {
    "ctr_delta_pct": -0.32,
    "last_ctr": 0.0123,
    "ctr_baseline": 0.0181,
    "roas_delta_pct": -0.15
  }
}
```

### Creatives Format

Recommendations tied to real problems:

```json
{
  "insight_id": "abc123",
  "hypothesis": "CTR has dropped by 32%...",
  "impact": "high",
  "creatives": [
    {
      "campaign": "WOMEN SEAMLESS EVERYDAY",
      "issue_diagnosed": "CTR 32% below baseline (0.0123 vs 0.0181)",
      "evidence": {
        "current_ctr": 0.0123,
        "baseline_ctr": 0.0181,
        "delta_pct": -32.0,
        "campaign_spend": 15234.50
      },
      "recommendations": [
        {
          "headline": "Refresh creative fatigue - emphasize seamless, comfort, everyday",
          "message": "Current CTR (1.23%) is 32% below baseline. Test new angles...",
          "cta": "Shop Now",
          "rationale": "Low CTR indicates ad fatigue. Campaign has spent $15,234..."
        }
      ]
    }
  ]
}
```

---

## How To Modify It

### Adding a New Metric

1. Update the Data Agent (`src/agents/data_agent.py`):
   ```python
   # In summarize_df(), add your metric
   grp = df.groupby("campaign").agg({
       "spend": "sum",
       "your_metric": "sum"  # Add here
   })
   ```

2. Add baseline computation (`src/utils/baseline.py`):
   ```python
   def compute_your_metric_baseline(df, window_days=30):
       # Your logic here
       ...
   ```

3. Update the Evaluator (`src/agents/evaluator.py`):
   ```python
   # Add to evidence calculation
   evidence["your_metric_delta"] = ...
   ```

4. Configure thresholds (`config/config.yaml`):
   ```yaml
   your_metric_threshold: 0.15
   ```

### Adding a New Hypothesis Type

Update the Insight Agent (`src/agents/insight_agent.py`):

```python
# In generate_insights(), add your logic
if your_condition:
    h = {
        "id": _make_id(),
        "hypothesis": "Your hypothesis with evidence",
        "metrics_used": ["your_metric"],
        "initial_confidence": 0.7,
        "evidence_hint": {"your_metric_delta": delta}
    }
    out.append(h)
    
    # Log why you generated this
    log_decision("insight_agent", "generated_your_hypothesis", 
                 "Why this matters", context)
```

---

## Debugging

### Understanding The Logs

Everything gets logged to `logs/observability/` with timestamps:

- `orchestrator_run_started_*.json` - Pipeline started
- `data_agent_load_started_*.json` - Loading CSV
- `insight_agent_decision_*.json` - Why each hypothesis was generated
- `evaluator_validate_completed_*.json` - Validation results
- `orchestrator_run_completed_*.json` - Pipeline finished

### Decision Logs Explain "Why"

```json
{
  "agent": "insight_agent",
  "event": "decision",
  "timestamp": "2025-12-05T00:55:57.569377Z",
  "payload": {
    "decision": "generated_roas_hypothesis",
    "rationale": "ROAS delta (-100%) exceeded threshold (-5%)",
    "context": {
      "roas_delta_pct": -1.0,
      "threshold": -0.05,
      "hypothesis_id": "abc123"
    }
  }
}
```

### When Things Go Wrong

1. Check `orchestrator_run_failed_*.json` for high-level errors
2. Look for `*_error_*.json` files for specific failures
3. Review `io_summary` logs to trace data flow
4. Check `schema_validation_failed_*.json` for data quality issues

---

## Your Data

### Required Columns

```
date, campaign_name, spend, impressions, clicks, revenue
```

### Optional Columns

```
purchases, roas, creative_message
```

Missing numeric fields get filled with 0.0 automatically. ROAS is recalculated when needed.

---

## The Agents Explained

### 1. Planner
Turns your question into an execution plan. No external calls, just parsing.

### 2. Data Agent
- Loads CSV (with sampling, chunking, missing column repair)
- Computes global metrics and campaign-level stats
- Validates schema and detects drift
- Writes schema fingerprint to `reports/schema_fingerprint.json`

### 3. Insight Agent
Generates hypotheses about:
- ROAS decline
- Creative fatigue (low CTR)
- Other performance issues

### 4. Evaluator
Validates each hypothesis:
- Checks CTR/ROAS thresholds
- Computes severity (critical/high/medium/low)
- Adjusts confidence scores
- Produces validation metrics

### 5. Creative Generator
Creates recommendations for low-performing campaigns.

### 6. Orchestrator
Runs everything in order, writes reports, captures metrics.

---

## Advanced Features

### LLM Output Validation

Location: `src/utils/llm_validation.py`

Handles messy AI responses:
- Checks for required fields and correct types
- Fixes out-of-range values (clamps confidence to 0.0-1.0)
- Repairs common JSON issues (trailing commas, missing brackets)
- Retries with exponential backoff (1s, 2s, 4s)
- Logs all validation failures and repairs

### Large File Support

In `config/config.yaml`:
```yaml
chunksize: 10000  # Load 10k rows at a time
```

Processes multi-GB files without running out of memory.

### Edge Case Testing

37 tests in `tests/test_edge_cases.py` and `tests/test_llm_validation.py` covering:
- Empty/malformed data
- NaN and infinity handling
- Zero division scenarios
- Missing columns
- LLM output validation
- Retry mechanisms

---

## Configuration

Key settings in `config/config.yaml`:

```yaml
chunksize: null        # Set to 10000+ for huge files
window_days: 30        # How far back to look for baselines
confidence_min: 0.5    # Minimum confidence to pass validation
strict_schema_validation: false
```

---

## Tests

Run all 49 tests:

```bash
make test
# or
PYTHONPATH="$(pwd)" pytest -v
```

**What's tested:**
- ✅ All 6 agents
- ✅ Orchestrator integration
- ✅ Dynamic thresholds and baseline computation
- ✅ Schema validation and drift detection
- ✅ 30 edge cases (empty data, NaN/infinity, missing columns, zero division)
- ✅ 19 LLM validation tests (malformed output, retry logic, JSON repair)

---

## What Changed in v2.0

### P0 (Must Have)
- ✅ Enhanced validation with severity classification
- ✅ Comprehensive observability with decision logs
- ✅ Metrics capture for data flow

### P1 (Should Have)
- ✅ Dynamic thresholds from historical data
- ✅ Expanded test coverage (12 → 49 tests)
- ✅ LLM output validation with retry logic

### P2 (Nice to Have)
- ✅ Schema versioning and drift detection
- ✅ Chunked CSV loading for huge files
- ✅ Alert rules for performance swings

**Bottom line:** This version handles real-world messiness instead of assuming perfect data.

---

## License

MIT
