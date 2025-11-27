# Kasparro Agentic FB Analyst – Kiran Biradar

End-to-end, fully local, agentic pipeline for analyzing Facebook Ads performance using a multi-agent architecture (Planner → Data Agent → Insight Agent → Evaluator → Creative Generator) coordinated through an orchestrator.  
No external APIs required. No internet dependencies.

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
│   └── (runtime logs)
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
│   └── observability/
│       ├── trace_example.json
│       └── (agent traces)
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
│       └── retry_utils.py
│
├── tests/
│   ├── test_planner.py
│   ├── test_data_agent.py
│   ├── test_insight_agent.py
│   ├── test_evaluator.py
│   ├── test_creative_generator.py
│   └── test_orchestrator.py
│
├── .env
├── Makefile
├── run.py
├── requirements.txt
├── PR_SELF_REVIEW.md
└── EVAL_CHECKLIST.md
```

---

## 2. Environment Setup

### **Conda environment (recommended & required for Apple Silicon)**

```bash
conda create -n kasparro python=3.11 -y
conda activate kasparro
pip install -r requirements.txt
```

Verify:

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

Run the agentic system:

```bash
python run.py "Analyze ROAS drop in last 7 days"
```

Outputs generated to:

```
reports/insights.json
reports/creatives.json
reports/report.md
```

---

## 4. Makefile Commands (Optional but Recommended)

```makefile
run:
	python run.py "Analyze ROAS drop in last 7 days"

test:
	PYTHONPATH="$(pwd)" pytest -q

lint:
	flake8 src

clean:
	rm -rf __pycache__ */__pycache__
```

Use:

```bash
make run
make test
make clean
```

---

## 5. Sample Data

A truncated & sanitized sample of the original dataset was placed at:

```
data/sample_fb_ads.csv
```

Schema includes:

```
date, campaign_name, adset_name, spend, impressions, clicks, revenue, roas
```

Used for deterministic offline testing.

---

## 6. Multi-Agent Architecture

### **1. Planner**
Breaks user query into actionable steps.  

### **2. Data Agent**
Loads CSV → preprocesses → computes aggregates.

### **3. Insight Agent**
Generates hypotheses about performance drivers.

### **4. Evaluator**
Scores hypotheses & adjusts confidence.

### **5. Creative Generator**
Produces creative recommendations based on insights.

### **6. Orchestrator**
Coordinates all agents into a pipeline and writes outputs.

---

## 7. Running Tests

The entire pipeline has full test coverage.

Run:

```bash
PYTHONPATH="$(pwd)" pytest -q
```

Expected:

```
6 passed in 0.55s
```

---

## 8. Observability Traces

Agent-level traces live under:

```
reports/observability/
```

Example:

- step-level execution  
- input/output logs  
- timing metadata  


---

## 9. Self-Review (PR_SELF_REVIEW.md)

This file documents:

- what was implemented  
- reasoning behind design decisions  
- tradeoffs & future improvements  

---

## 10. Evaluation Checklist (EVAL_CHECKLIST.md)


- modular  
- deterministic  
- no API dependencies  
- reproducible  
- hypothesis → evaluation → creatives pipeline is correct  

---

## 11. Notes

- Project is 100% offline  
- No external APIs  
- Deterministic outputs using static data  
- Architecture mirrors real production agentic design  

---

## 12. License

MIT.

