.PHONY: help install check create-user api web dev seed e2e test fmt lint clean

help:
	@echo "make install      install backend + frontend dependencies"
	@echo "make check        verify OpenAI, Slack, and the users file"
	@echo "make create-user  create a dashboard login in data/users.json (u=username p=password)"
	@echo "make api          run the backend, including the Slack listener"
	@echo "make web          run the frontend only (needs frontend/)"
	@echo "make dev          run backend (+ frontend, once frontend/ exists)"
	@echo "make seed         load a canned conversation into the running backend (c=CHANNEL_ID)"
	@echo "make e2e          run INGEST+PLAN for real and check the result (c=CHANNEL_ID)"
	@echo "make test         run the backend test suite"
	@echo "make fmt          format and autofix"

# Phase 1 has no frontend/ yet — it is added back once one exists, so
# `make install`/`make dev` work today and pick it up automatically later.
install:
	cd backend && pip install -r requirements.txt
	@if [ -d frontend ]; then cd frontend && npm install; else \
		echo "frontend/ not present yet; skipping npm install"; fi

check:
	cd backend && python -m scripts.check_creds $(ARGS)

create-user:
	@test -n "$(u)" && test -n "$(p)" || (echo "usage: make create-user u=alice p=secret" && exit 1)
	cd backend && python -m scripts.create_user --username $(u) --password $(p)

api:
	cd backend && python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

web:
	@if [ -d frontend ]; then cd frontend && npm run dev; else \
		echo "frontend/ not present yet; nothing to run" && exit 1; fi

dev:
	@if [ -d frontend ]; then \
		trap 'kill 0' EXIT; \
		( cd backend && python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 ) & \
		( cd frontend && npm run dev ) & \
		wait; \
	else \
		echo "frontend/ not present yet; running the backend only"; \
		cd backend && python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000; \
	fi

seed:
	@test -n "$(c)" || (echo "usage: make seed c=C0123456789" && exit 1)
	cd backend && python -m scripts.seed --channel $(c) --reset

e2e:
	@test -n "$(c)" || (echo "usage: make e2e c=C0123456789" && exit 1)
	cd backend && python -m scripts.e2e --channel $(c)

test:
	cd backend && python -m pytest -q

fmt:
	cd backend && python -m ruff format . && python -m ruff check --fix .

lint:
	cd backend && python -m ruff check .

clean:
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	rm -rf backend/.pytest_cache backend/.ruff_cache
