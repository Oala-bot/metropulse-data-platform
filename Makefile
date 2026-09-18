.PHONY: setup check frontend download profile db migrate load warehouse api
setup:
	uv sync --locked
	npm --prefix frontend ci
check:
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy
	npm --prefix frontend run lint
	npm --prefix frontend run format:check
	npm --prefix frontend run typecheck
	npm --prefix frontend run build
frontend:
	npm --prefix frontend run dev
download:
	uv run python -m ingestion.download --year 2025 --month 1 --taxi-type yellow
profile:
	uv run python -m ingestion.profile data/raw/yellow_tripdata_2025-01.parquet --output data/processed/january-2025-profile.json
db:
	docker compose up -d --wait postgres
migrate:
	uv run alembic upgrade head
load:
	uv run python -m ingestion.load --year 2025 --month 1
warehouse:
	uv run python -m backend.app.database.warehouse
api:
	uv run uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000 --no-access-log
