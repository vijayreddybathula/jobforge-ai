.PHONY: install install-api install-ui dev dev-api dev-ui test lint

# ── Python / API ────────────────────────────────────────────────────────────
install-api:
	poetry install

dev-api:
	uvicorn apps.web.main:app --reload --host 0.0.0.0 --port 8000

test:
	poetry run pytest

lint:
	poetry run ruff check .
	poetry run black --check .

# ── Node / Frontend ─────────────────────────────────────────────────────────
install-ui:
	cd apps/web-ui && npm install

dev-ui:
	cd apps/web-ui && npm run dev

build-ui:
	cd apps/web-ui && npm run build

# ── Combined ────────────────────────────────────────────────────────────────
install: install-api install-ui
	@echo "\n✅  All dependencies installed."
	@echo "   API:  poetry install (bcrypt already in pyproject.toml)"
	@echo "   UI:   npm install (in apps/web-ui)"

dev:
	@echo "Start two terminals:"
	@echo "  make dev-api   — FastAPI on :8000"
	@echo "  make dev-ui    — Vite on :5173"
