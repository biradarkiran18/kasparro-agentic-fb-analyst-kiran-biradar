# Agentic FB Ads Analytics Pipeline – Kiran Biradar (v1.3)

[![Python](https://img.shields.io/badge/python-3.11-blue.svg)]()
[![Tests](https://img.shields.io/badge/tests-passing-brightgreen.svg)]()
[![Status](https://img.shields.io/badge/build-stable-lightgrey.svg)]()

A fully local, deterministic pipeline for analyzing Facebook Ads performance.  
The system is built around a set of cooperating agents (Planner → Data → Insight → Evaluator → Creative Generator) orchestrated in a reproducible, test-driven workflow.  
All computations run offline. No API calls. No external services.

Version **v1.3** includes:

- Dynamic CTR / ROAS threshold computation from historical data  
- Schema fingerprinting + drift detection  
- Full observability (per-agent logs, orchestrator traces, alerts)  
- Hardened evaluator and data agent  
- Eight core tests + schema tests + threshold tests  
- Fully flake8-clean  
- 100% deterministic and reproducible

---

## 1. Project Structure

```
kasparro-agentic-fb-analyst-kiran-biradar/
│
├── config/
│   └── config.yaml
│
├── data/
│   └── sample_fb_ads.csv
│
├── logs/
│   ├── .gitkeep
│   └── observability/
│       ├── orchestrator_run_started_*.json
│       ├── orchestrator_run_completed_*.json
│       ├── trace_orchestrator_*.json
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
│   ├── insights.json
│   ├── creatives.json
│   ├── report.md
│   ├── metrics.json
│   └── schema_fingerprint.json
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
│   │   └── orchestrator.py
│   │
│   └── utils/
│       ├── io_utils.py
│       ├── observability.py
│       ├── retry_utils.py
│       ├── thresholds.py
│       └── schema.py
│
├── tests/
│   ├── test_planner.py
│   ├── test_data_agent.py
│   ├── test_insight_agent.py
│   ├── test_evaluator.py
│   ├── test_creative_generator.py
│   ├── test_orchestrator.py
│   ├── test_thresholds.py
│   └── test_schema.py
│
├── Makefile
├── pytest.ini
├── run.py
├── requirements.txt
├── PR_SELF_REVIEW.md
└── README.md
```

---

## 2. Environment Setup

### Create Conda Environment

```bash
conda create -n kasparro python=3.11 -y
conda activate kasparro
pip install -r requirements.txt
```

### Verify

```bash
python --version
python - << 'EOF'
import pandas as pd, numpy as np
print(pd.__version__)
print(np.__version__)
EOF
```

Expected:

```
pandas 1.5.3
numpy 1.26.4
```

---

## 3. Running the Pipeline

```bash
python run.py "Analyze ROAS drop in last 7 days"
```

Outputs written to:

```
reports/insights.json
reports/creatives.json
reports/report.md
reports/metrics.json
reports/schema_fingerprint.json
logs/observability/*.json
```

---

## 4. Makefile Commands

```makefile
run:
	python run.py "Analyze ROAS drop in last 7 days"

test:
	PYTHONPATH="$(pwd)" pytest -q

lint:
	flake8 src tests --max-line-length=120

format:
	autopep8 --in-place --recursive --max-line-length 120 src tests

all:
	make format && make lint && make test && make run
```

Usage:

```bash
make test
make lint
make run
make all
```

---

## 5. Dataset Schema

Expected columns:

```
date, campaign_name, spend, impressions, clicks, revenue, creative_message
```

Optional:

```
purchases, roas
```

Missing numeric fields are filled automatically. ROAS is recomputed safely whenever needed.

---

## 6. Agents

### 1. Planner  
Produces a small, deterministic “plan” describing pipeline steps.  
No external calls.

### 2. Data Agent  
Loads CSV with:
- sampling  
- chunking  
- missing-column repair  

Computes:
- global metrics  
- daily ROAS  
- campaign-level aggregates  
- CTR and ROAS per campaign  

Writes a schema fingerprint to:

```
reports/schema_fingerprint.json
```

### 3. Insight Agent  
Generates structured hypotheses:
- ROAS decline  
- Creative fatigue  
- Other basic performance signals  

### 4. Evaluator  
Hardened logic:
- safe float parsing  
- CTR threshold check  
- ROAS drop detection  
- traceable notes  
- confidence readjustment  
- produces validation metrics  

### 5. Creative Generator  
Simple token-based recommendation module for low-CTR campaigns.

### 6. Orchestrator  
Controls all agents, writes reports, metrics, traces, alerts, and returns:

```
(validated_hypotheses, creatives)
```

---

## 7. Dynamic Thresholds (CTR & ROAS)

Implemented in:

```
src/utils/thresholds.py
```

- Computes baseline CTR from daily data  
- Produces statistically valid CTR-low threshold  
- Computes ROAS drop threshold using negative-day deltas  
- Auto-fallback to config thresholds if insufficient history  

Orchestrator integrates via:

```python
dyn = compute_dynamic_thresholds(df, ...)
```

---

## 8. Schema Fingerprinting & Drift Detection

Implemented in:

```
src/utils/schema.py
```

Pipeline checks for drift automatically and writes:

```
reports/schema_fingerprint.json
```

Test coverage ensures:
- matching schemas produce identical hashes  
- changed schemas trigger drift  
- added/removed columns are detected  

---

## 9. Observability

All logs stored in:

```
logs/observability/
```

Categories:
- run_started  
- run_completed  
- data load events  
- evaluator start/end  
- alerts.json  
- full per-run trace file  

Every entry includes correlation_id + timestamp.

---

## 10. Metrics

Written to:

```
reports/metrics.json
```

Includes:

```json
{
  "query": "...",
  "start_ts": "...",
  "run_ts": "...",
  "duration_ms": 421,
  "num_hypotheses": 2,
  "num_validated": 1,
  "validation_rate": 0.5,
  "num_creatives": 3,
  "rows_in_input": 5000,
  "metrics_version": "v1"
}
```

---

## 11. Tests

Run:

```bash
PYTHONPATH="$(pwd)" pytest -q
```

Expected:

```
all tests passed
```

The suite covers:
- planner structure  
- data loading & summarization  
- hypothesis generation  
- evaluator threshold logic  
- creative generation  
- orchestrator smoke test  
- dynamic thresholds  
- schema drift detection  

---

## 12. Self-Review Notes

Documented in:

```
PR_SELF_REVIEW.md
```

Covers:
- design decisions  
- tradeoffs  
- limitations  
- how the system would scale in a production environment  

---

## 13. Summary of v1.3 Changes

- Dynamic threshold computation (CTR / ROAS) added  
- Schema fingerprinting written + drift detection added  
- Orchestrator updated with fallback logic and alerts  
- Tests expanded (thresholds + schema)  
- Codebase fully formatted and lint-clean  
- All tests green  
- Full observability pipeline in place  

---

## 14. License

MIT.