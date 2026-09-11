.PHONY: help install db db-stop check migrate revision api slack web dev seed e2e test fmt lint clean

help:
	@echo "make install   install backend + frontend dependencies"
	@echo "make db        start Postgres (docker compose)"
	@echo "make check     verify every API credential"
	@echo "make migrate   apply database migrations"
	@echo "make revision  autogenerate a migration (m=\"message\")"
	@echo "make api       run the backend only"
	@echo "make slack     run the Slack listener only"
	@echo "make web       run the frontend only"
	@echo "make dev       run backend + Slack listener + frontend together"
	@echo "make seed      load a canned conversation (c=CHANNEL_ID)"
	@echo "make e2e       run the full pipeline for real and check the result (c=CHANNEL_ID)"
	@echo "make test      run the backend test suite"
	@echo "make fmt       format and autofix"

install:
	cd backend && uv sync
	cd frontend && npm install

db:
	docker compose up -d db
	@echo "waiting for postgres..."
	@until docker compose exec -T db pg_isready -U pmfyp -d pmfyp >/dev/null 2>&1; do sleep 1; done
	@echo "postgres ready on localhost:5433"

db-stop:
	docker compose down

check:
	cd backend && uv run python -m scripts.check_creds $(ARGS)

migrate:
	cd backend && uv run alembic upgrade head

revision:
	cd backend && uv run alembic revision --autogenerate -m "$(m)"

slack:
	cd backend && uv run python -m app.slack_runner

api:
	cd backend && uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

web:
	cd frontend && npm run dev

dev:
	@trap 'kill 0' EXIT; \
	( cd backend && uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 ) & \
	( cd backend && uv run python -m app.slack_runner ) & \
	( cd frontend && npm run dev ) & \
	wait

seed:
	@test -n "$(c)" || (echo "usage: make seed c=C0123456789" && exit 1)
	cd backend && uv run python -m scripts.seed --channel $(c) --reset

e2e:
	@test -n "$(c)" || (echo "usage: make e2e c=C0123456789" && exit 1)
	cd backend && uv run python -m scripts.e2e --channel $(c)

test:
	cd backend && uv run pytest -q

fmt:
	cd backend && uv run ruff format . && uv run ruff check --fix .

lint:
	cd backend && uv run ruff check .

clean:
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	rm -rf backend/.pytest_cache backend/.ruff_cache
