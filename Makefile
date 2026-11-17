.PHONY: install run test lint format typecheck eval eval-strict check clean

# Code server nằm trong server/ (ADR-0001). Lệnh chạy từ gốc repo.
install:
	pip install -r server/requirements.txt

run:
	cd server && uvicorn app.main_api:app --app-dir src --reload --host 0.0.0.0 --port 8000

test:
	cd server && pytest -v

# Eval regression — deliverable #10, report ở eval/results/report.md. Không cần API key.
eval:
	python3 eval/run_eval.py

eval-strict:
	python3 eval/run_eval.py --strict

lint:
	cd server && ruff check src/ tests/

format:
	cd server && ruff format src/ tests/

typecheck:
	cd server && mypy src/

check: lint test

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .pytest_cache -exec rm -rf {} +
	find . -type d -name .ruff_cache -exec rm -rf {} +
