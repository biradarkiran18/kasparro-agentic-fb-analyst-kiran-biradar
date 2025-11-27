# Self-review — Kasparro Agentic FB Analyst

## What I built
- Modular pipeline: planner, data-agent, insight-agent, evaluator, creative-generator, orchestrator.
- Sample dataset (500 rows) with config toggle to switch between sample and full dataset.
- Tests covering each agent (6 passed).
- Generated output: reports/insights.json, reports/creatives.json, reports/report.md.
- Observability example stored under reports/observability/.

## How it meets the assignment brief
- Required artifacts included.
- LLM-first agent flow implemented.
- Reproducibility instructions present.
- Clear modular structure.

## Known limitations
- Creative generator uses rule patterns.
- Insight validation is minimal; can be extended with real LLM scoring.

## Recommended next steps
1. Add Langfuse observability.
2. Add RAG-based creative inspiration.
3. Add CI to run tests and publish artifacts.
