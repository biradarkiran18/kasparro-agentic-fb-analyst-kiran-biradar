.PHONY: run test lint format clean

run:
	python run.py "Analyze ROAS drop in last 7 days"

test:
	PYTHONPATH="$(pwd)" pytest -q

lint:
	flake8 src tests --max-line-length=120 || true

format:
	autopep8 --in-place --recursive --max-line-length 120 src tests || true

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	rm -f pytest_output.txt run_report.txt
	