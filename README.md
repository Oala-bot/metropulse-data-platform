# MetroPulse

NYC Yellow Taxi analytics and demand forecasting. Downloads, validates, quarantines, and loads monthly trips into PostgreSQL. The API, analytics models, forecasts, and dashboard are still to be built.

## Setup

Requires uv, Node.js 22.12+, and Docker Desktop running.

```bash
uv sync --locked
cp .env.example .env
# Set a local password in POSTGRES_PASSWORD and DATABASE_URL.
docker compose up -d --wait postgres
uv run alembic upgrade head
npm --prefix frontend ci
npm --prefix frontend run dev
```

Frontend: http://localhost:5173. PostgreSQL listens only on localhost. `docker compose down` stops it without deleting data.

## Load data

Source: [NYC TLC](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page). Initial scope: January–March 2025.

```bash
uv run python -m ingestion.load --year 2025 --month 1
```

Change `--month` to 2 or 3. The loader downloads missing files and zone lookups, reads `.env`, and commits a month atomically. `--file path.parquet` uses a local file; `--zones path.csv` uses a local zone lookup. Exact completed files are skipped; unique trip keys also prevent duplicate rows within and across loads. Concurrent loads are refused.

Records with missing required values, unknown zones, invalid payment codes, out-of-month pickups, durations outside (0, 24 hours], distances outside [0, 1,000 miles], or monetary fields outside [0, $10,000] are quarantined. Negative charges may be genuine reversals; this project's analytics exclude them. Payment code `0` is a valid Flex Fare trip in the 2025 TLC dictionary. Missing passenger counts and optional charges stay null. These limits are project rules, not TLC guarantees.

`staging.trip` holds accepted trips; `load_batch` tracks counts and failures; `data_quality_result` tracks each rule. `rows_read = rows_accepted + rows_rejected + duplicate_rows` for successful batches. Quarantine JSONL files under `data/rejected/` retain source values, row numbers, and reasons; counts per rule can overlap. Failed loads commit no trips. A killed loader is marked failed when the next load starts.

Trip keys hash the normalized source fields (including timestamps, zones, and charges), excluding load metadata. Two legitimate trips with identical values can share a key. Source timestamps remain timezone-naive New York local time. Revised files append unseen keys; they do not overwrite previously accepted trips.

Raw data, quarantine files, generated profiles, and `.env` are Git-ignored. `make profile` profiles a downloaded January file. The standalone downloader still uses exported environment variables or CLI flags rather than reading `.env`.

## Checks

```bash
make check
```
