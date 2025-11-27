
.PHONY: setup run test clean release

CONDA_ENV := kasparro
PY := $(shell which python)
PYTHONPATH := $(shell pwd)

setup:
	@echo "Create conda env (if not exists) and install python deps"
	@echo "If you already have conda env, skip creation."
	@conda create -n $(CONDA_ENV) python=3.11 -y -c conda-forge || true
	@echo "Activate env and install packages from requirements"
	@bash -lc "conda activate $(CONDA_ENV) && pip install --upgrade pip && pip install -r requirements.txt"

run:
	@echo "Run pipeline (uses active python)."
	@bash -lc 'PYTHONPATH="$(PYTHONPATH)" python run.py "Analyze ROAS drop in last 7 days"'

test:
	@echo "Run tests"
	@bash -lc 'PYTHONPATH="$(PYTHONPATH)" pytest -q'

clean:
	@echo "Remove generated reports"
	@rm -rf reports/* || true

release:
	@echo "Create git tag v1.0 and push (remote must be configured)"
	@git add .
	@git commit -m "release: v1.0" || true
	@git tag -f v1.0
	@git push origin --tags
