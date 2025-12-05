.PHONY: setup run test clean

setup:
	pip install -r requirements.txt

run:
	python run.py

test:
	PYTHONPATH=$$(pwd) pytest tests/ -v

test-quick:
	PYTHONPATH=$$(pwd) pytest tests/ -q

test-coverage:
	PYTHONPATH=$$(pwd) pytest tests/ --cov=src --cov-report=html

lint:
	flake8 src tests --max-line-length=120 || true

format:
	autopep8 --in-place --recursive --max-line-length 120 src tests || true

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -f pytest_output.txt run_report.txt
	rm -rf htmlcov/ .coverage .pytest_cache/
	