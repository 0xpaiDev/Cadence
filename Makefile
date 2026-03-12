.PHONY: help test test-all test-schema test-context test-fetch test-agent test-api test-negotiate test-tasks test-webapp fetch pipeline serve serve-prod check-state lint init-vault install clean commit push install-service setup-cron check-logs status webapp-install webapp-build webapp-dev

help:
	@echo "Cadence Development Commands"
	@echo ""
	@echo "Testing:"
	@echo "  make test              Run all fast tests (excludes slow API calls)"
	@echo "  make test-all          Run all tests including slow agent tests"
	@echo "  make test-schema       Schema validation tests only"
	@echo "  make test-context      Context builder tests"
	@echo "  make test-fetch        Fetcher tests"
	@echo "  make test-agent        Agent output tests"
	@echo "  make test-api          API endpoint tests"
	@echo "  make test-negotiate    Negotiation session tests"
	@echo "  make test-tasks        Task + day lifecycle tests"
	@echo "  make test-webapp       Launch browser for webapp testing (start server first)"
	@echo ""
	@echo "Pipeline:"
	@echo "  make fetch             Run all fetchers now (news + calendar)"
	@echo "  make pipeline          Run full pipeline: fetch → context → draft"
	@echo ""
	@echo "Server:"
	@echo "  make serve             Start API server (dev mode with --reload)"
	@echo "  make serve-prod        Start API server (production)"
	@echo ""
	@echo "Utilities:"
	@echo "  make check-state       Check state file freshness"
	@echo "  make lint              Run type checking (mypy + ruff)"
	@echo "  make init-vault        Initialize vault directory structure"
	@echo "  make install           Install dev dependencies"
	@echo "  make clean             Remove build artifacts, caches, logs"
	@echo ""
	@echo "Automation (Phase 9):"
	@echo "  make install-service   Install systemd service (sudo required)"
	@echo "  make setup-cron        Install pipeline cron entry (crontab)"
	@echo "  make check-logs        Tail vault log files"
	@echo "  make status            Show systemd + cron + vault status"
	@echo ""
	@echo "Git:"
	@echo "  make commit            Stage all changes and commit (prompts for message)"
	@echo "  make push              Push commits to origin (requires message arg: make push MSG='...')"

install:
	pip install -e ".[dev]"

test:
	pytest -k "not slow" -v

test-all:
	pytest -v

test-schema:
	pytest tests/test_schemas.py -v

test-context:
	pytest tests/test_context_builder.py -v

test-fetch:
	pytest tests/test_fetchers.py -v

test-agent:
	pytest tests/test_agent_output.py -v

test-api:
	pytest tests/test_api.py -v

test-negotiate:
	pytest tests/test_negotiation.py -v

test-tasks:
	pytest tests/test_task_lifecycle.py tests/test_day_lifecycle.py -v

test-webapp:
	playwright-cli open http://localhost:8420/app/ --headed

webapp-install:
	cd webapp && npm install

webapp-build:
	cd webapp && npm run build

webapp-dev:
	cd webapp && npm run dev

fetch:
	python3 -m scripts.fetch.fetch_all

pipeline:
	python3 -m scripts.pipeline

serve:
	uvicorn api.server:app --host 0.0.0.0 --port 8420 --reload

serve-prod:
	uvicorn api.server:app --host 0.0.0.0 --port 8420

check-state:
	python3 -c "import scripts.config; print('State files check: TODO')"

init-vault:
	@echo "Initializing vault directory at ~/vault/"
	@mkdir -p ~/vault/{Daily,Projects,Knowledge}
	@mkdir -p ~/vault/data/{tasks,training}
	@mkdir -p ~/vault/.system/{state,context,drafts,config,logs,model}
	@touch ~/vault/data/tasks/inbox.md
	@touch ~/vault/data/tasks/today.md
	@touch ~/vault/data/tasks/backlog.md
	@touch ~/vault/data/training/plan.md
	@touch ~/vault/data/training/log.md
	@echo "✓ Vault structure created"
	@echo "Next: Add google_credentials.json to ~/vault/.system/config/"

lint:
	mypy scripts api tests || true
	ruff check . --fix || true

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache .coverage htmlcov
	rm -rf build dist *.egg-info
	find . -type f -name "*.log" -delete

install-service:
	@echo "Installing systemd service cadence-api..."
	@if [ ! -f deploy/cadence-api.service ]; then \
		echo "Error: deploy/cadence-api.service not found"; \
		exit 1; \
	fi
	sudo cp deploy/cadence-api.service /etc/systemd/system/
	sudo systemctl daemon-reload
	sudo systemctl enable cadence-api.service
	@echo "✓ Service installed and enabled"
	@echo "Run: sudo systemctl start cadence-api"

setup-cron:
	@echo "Installing pipeline cron entry..."
	@if ! command -v crontab &> /dev/null; then \
		echo "Error: crontab not found"; \
		exit 1; \
	fi
	@if [ ! -f deploy/crontab.txt ]; then \
		echo "Error: deploy/crontab.txt not found"; \
		exit 1; \
	fi
	@# Remove old cadence entries, then add new ones
	@crontab -l 2>/dev/null | grep -v "cadence\|Cadence" > /tmp/crontab_temp || true
	@cat deploy/crontab.txt >> /tmp/crontab_temp
	@crontab /tmp/crontab_temp
	@rm /tmp/crontab_temp
	@echo "✓ Cron entry installed"
	@echo "View: crontab -l"

check-logs:
	@vault_path=$$(grep '^path' cadence.toml | awk -F'"' '{print $$2}'); \
	if [ -z "$$vault_path" ]; then vault_path="/home/shu/vault"; fi; \
	echo "=== Pipeline Log ==="; \
	tail -20 "$$vault_path/.system/logs/pipeline.log" 2>/dev/null || echo "No pipeline log yet"; \
	echo ""; \
	echo "=== API Log ==="; \
	tail -20 "$$vault_path/.system/logs/api.log" 2>/dev/null || echo "No API log yet"

status:
	@echo "=== Systemd Service ===" && \
	systemctl status cadence-api 2>/dev/null || echo "Service not installed (run: make install-service)"; \
	echo ""; \
	echo "=== Cron Entry ===" && \
	crontab -l 2>/dev/null | grep -i cadence || echo "No cron entry found (run: make setup-cron)"; \
	echo ""; \
	echo "=== Vault Status ===" && \
	vault_path=$$(grep '^path' cadence.toml | awk -F'"' '{print $$2}'); \
	if [ -z "$$vault_path" ]; then vault_path="/home/shu/vault"; fi; \
	if [ -d "$$vault_path/.system" ]; then \
		echo "Vault: OK ($$vault_path)"; \
		echo "State files:"; \
		ls -lh "$$vault_path/.system/state/" 2>/dev/null | tail -5; \
	else \
		echo "Vault: NOT FOUND ($$vault_path)"; \
	fi

commit:
	@git status
	@echo ""
	@read -p "Commit message: " msg; \
	git add -A && git commit -m "$$msg"

push:
	@if [ -z "$(MSG)" ]; then \
		echo "Error: Commit message required"; \
		echo "Usage: make push MSG='Your commit message'"; \
		exit 1; \
	fi
	git add -A && git commit -m "$(MSG)" && git push origin main
