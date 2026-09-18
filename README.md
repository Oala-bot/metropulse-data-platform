# MetroPulse

NYC Yellow Taxi analytics and demand forecasting. Monthly trips are validated, loaded into PostgreSQL, transformed with dbt, and served through FastAPI. The React dashboard, forecasting model, and Airflow orchestration are still to be built.

## Setup

Requires uv, Node.js 22.12+, and Docker Desktop running.

```bash
uv sync --locked
cp .env.example .env
# Set POSTGRES_PASSWORD, the matching DATABASE_URL, and a random ADMIN_API_KEY.
docker compose up -d --wait postgres
uv run alembic upgrade head
uv run python -m ingestion.load --year 2025 --month 1
uv run python -m backend.app.database.warehouse
uv run uvicorn backend.app.main:app --reload --no-access-log
```

If `.env` already exists, keep it. API: http://localhost:8000. Interactive API reference: http://localhost:8000/docs. `make api`, `make warehouse`, and `make check` are shortcuts. PostgreSQL is bound to localhost; `docker compose down` stops it without deleting data.

For the frontend starter page: `npm --prefix frontend ci`, then `npm --prefix frontend run dev`.

## Data

Source: [NYC TLC](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page). Initial scope: January–March 2025. Change `--month` to load another month, then rebuild the warehouse.

The loader reads `.env`; `--file path.parquet` and `--zones path.csv` use local inputs. Identical completed files are skipped. Unique trip keys prevent repeated rows; failed monthly loads commit no trips. Quarantine files under `data/rejected/` retain source values, row numbers, and reasons. Raw files and credentials are Git-ignored.

Validation rejects missing required values, unknown zones, invalid payment codes, out-of-month pickups, durations outside (0, 24 hours], distances outside [0, 1,000 miles], and monetary fields outside [0, $10,000]. These are project rules. Negative charges may be genuine reversals, but are excluded here. Payment code `0` is Flex Fare. Missing passenger counts and optional charges stay null.

Trip keys hash normalized source fields, excluding load metadata. Identical legitimate trips can share a key. Revised files append unseen keys rather than replacing old records. Times remain New York local time without timezone offsets.

## API

```bash
curl 'http://localhost:8000/api/v1/summary?start_date=2025-01-01&end_date=2025-01-31'
curl 'http://localhost:8000/api/v1/zones/top?direction=pickup&limit=10'
curl 'http://localhost:8000/api/v1/trends/hourly?zone_id=161&limit=24'
```

Dates are inclusive and filter trip pickup time. `zone_id` filters pickup zones, except for zone rankings/details where it identifies the selected pickup or drop-off zone. Paginated routes return `items`, `total`, `limit`, and `offset`. Revenue means recorded total charges, not profit. Weighted averages use trip counts.

Other routes: `/health`, `/api/v1/trends/daily`, `/api/v1/zones/{zone_id}`, `/api/v1/payment-types`, `/api/v1/forecasts`, `/api/v1/models/latest`, and `/api/v1/pipeline-runs[/{run_id}]`. Forecasts return an empty list and the latest model is null until training is implemented.

`POST /api/v1/admin/ingest/{year}/{month}` requires `X-API-Key` matching `ADMIN_API_KEY`. It returns a run ID immediately; poll `/api/v1/pipeline-runs/{run_id}` for download, load, and warehouse status. Only one API ingestion runs at a time. Worker logs are in `logs/`. Failed or interrupted workers can be retried; stale runs are marked failed when a new request starts.

Migrations own operational/staging tables and forecast storage. dbt owns the `analytics` dimensions, facts, and marts. No automated test suite is included.
