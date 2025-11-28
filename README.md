# Kasparro Agentic FB Analyst – Kiran Biradar (v1.1)

A fully local, production-grade, multi-agent pipeline for analyzing Facebook Ads performance.  
Implements a complete agent chain (Planner → Data → Insight → Evaluator → Creative Generator) with strong observability, schema validation, reproducibility, and deterministic outputs.

This is v1.1 — upgraded:
- Evaluator hardening (threshold control, structured metrics, reliability)
- Schema fingerprinting + drift detection
- Detailed observability logs (start/end events, per-agent traces)
- End-to-end metrics (duration, counts, validation rate)
- More modular configuration
- Deterministic rule-based logic
- Improved orchestrator with trace IDs

No APIs. No external dependencies. 100% offline and reproducible.

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
│   └── observability/
│       ├── orchestrator_run_started_*.json
│       ├── orchestrator_run_completed_*.json
│       └── trace_orchestrator_*.json
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
│       ├── retry_utils.py
│       └── observability.py
│
├── tests/
│   ├── test_planner.py
│   ├── test_data_agent.py
│   ├── test_insight_agent.py
│   ├── test_evaluator.py
│   ├── test_creative_generator.py
│   └── test_orchestrator.py
│
├── Makefile
├── run.py
├── requirements.txt
├── PR_SELF_REVIEW.md
└── EVAL_CHECKLIST.md
```

---

## 2. Environment Setup

### Conda Environment
```bash
conda create -n kasparro python=3.11 -y
conda activate kasparro
pip install -r requirements.txt
```

Verify installation:

```bash
python --version
python -c "import pandas as pd; print(pd.__version__)"
```

Expected:
```
Python 3.11.x  
pandas 1.5.3  
```

---

## 3. Quick Start

Run the agent pipeline:

```bash
python run.py "Analyze ROAS drop in last 7 days"
```

Outputs generated:

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
	make format && make test && make run
```

Usage:

```bash
make test
make run
make format
make all
```

---

## 5. Dataset Information

Location:

```
data/sample_fb_ads.csv
```

Schema:

```
date, campaign_name, adset_name, spend, impressions, clicks, revenue, roas, creative_message
```

This dataset is a **sanitized, small-scale offline sample** for deterministic evaluation.

---

## 6. Multi-Agent Architecture

### **1. Planner**
Breaks the user’s natural-language query into actionable analysis steps.

### **2. Data Agent**
Loads CSV, computes ROAS, CTR, aggregates, and produces:
- global summary  
- campaign-level summary  

Includes schema fingerprinting to detect changes in input structure.

### **3. Insight Agent**
Generates structured hypotheses:
- ROAS decline
- Creative fatigue
- Other campaign anomalies

### **4. Evaluator (v1.1 upgrade)**
Strengthened evaluation logic:
- threshold-driven validation  
- CTR and ROAS-drop based scoring  
- final confidence scoring  
- returns both validated hypotheses and evaluation metrics  

### **5. Creative Generator**
Uses token frequency analysis from real creatives to generate recommendations.

### **6. Orchestrator (v1.1 upgrade)**
Coordinates all agents, writes:
- insights.json  
- creatives.json  
- report.md  
- metrics.json  
- observability traces  
- schema_fingerprint.json  

---

## 7. Tests

Run all tests:

```bash
PYTHONPATH="$(pwd)" pytest -q
```

Expected output:

```
8 passed in 0.50s
```

The test suite covers:
- hypothesis generation  
- evaluator correctness  
- creative generation  
- summarization logic  
- orchestrator end-to-end execution  

---

## 8. Observability (v1.1)

All agent steps produce structured logs stored in:

```
logs/observability/
```

Includes:
- run_started events  
- run_completed events  
- trace_orchestrator events  
- data_agent completion logs  
- timestamps, duration, and inputs/outputs  

---

## 9. Metrics (v1.1)

Stored at:

```
reports/metrics.json
```

Metrics include:
- query  
- start/end timestamps  
- duration_ms  
- number of hypotheses  
- validation rate  
- number of creatives generated  
- schema hash  

---

## 10. Schema Fingerprinting (v1.1)

Fingerprint written to:

```
reports/schema_fingerprint.json
```

Used to detect:
- column drift  
- schema mismatch  
- missing fields  

Enables production-grade reliability.

---

## 11. Self-Review (PR_SELF_REVIEW.md)

Includes:
- design decisions  
- tradeoffs  
- limitations  
- future roadmap  

---

## 12. Evaluation Checklist (EVAL_CHECKLIST.md)

Covers assignment requirements:
- structure  
- reproducibility  
- determinism  
- outputs  
- observability  
- testing  
- architecture clarity  

---

## 13. What Changed from v1.0 → v1.1

### **Evaluator Hardening**
- Higher-quality confidence handling  
- Validation metrics  
- Threshold-controlled logic  
- Deterministic scoring path  

### **Observability Framework**
- Per-agent logs  
- Orchestrator traces  
- Consistent timestamps  

### **Metrics Tracking**
- Runtime duration  
- Validation rate  
- Count of creatives  
- Hypothesis counts  

### **Schema Protection**
- Schema fingerprinting  
- JSON hash-based drift detection  

### **Cleaner Orchestrator**
- Shorter return signature  
- Expanded logging  
- Safer config handling  

### **Linting + Formatting Compliance**
- flake8 clean  
- autopep8 formatted  
- all tests passing  

---

## 14. License

MIT.
