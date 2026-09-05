# INR-x402 — developer entrypoints.
# PY resolves to the venv python on both Windows and POSIX layouts.
PY := $(if $(wildcard venv/Scripts/python.exe),venv/Scripts/python.exe,venv/bin/python)

.PHONY: help venv install demo test seed run-bank run-facilitator run-merchant clean

help:
	@echo "Targets:"
	@echo "  make venv     - create virtualenv"
	@echo "  make install  - create venv + install requirements"
	@echo "  make demo     - boot all services, seed, run the happy path e2e"
	@echo "  make test     - run the pytest suite (unit + 6 scenarios)"
	@echo "  make seed     - seed keys/user/mandate (services must be running)"
	@echo "  make clean    - remove local DBs and caches"

venv:
	python -m venv venv

install: venv
	$(PY) -m pip install --upgrade pip
	$(PY) -m pip install -r requirements.txt

demo:
	$(PY) -m scripts.run_demo

test:
	$(PY) -m pytest -q

seed:
	$(PY) -m scripts.seed

run-bank:
	$(PY) -m uvicorn mock_bank.app:app --host 127.0.0.1 --port 8003

run-facilitator:
	$(PY) -m uvicorn facilitator.app:app --host 127.0.0.1 --port 8002

run-merchant:
	$(PY) -m uvicorn merchant.app:app --host 127.0.0.1 --port 8001

clean:
	-rm -rf data/*.db data/*.db-wal data/*.db-shm data/agent_receipts.jsonl
	-rm -rf .pytest_cache **/__pycache__
