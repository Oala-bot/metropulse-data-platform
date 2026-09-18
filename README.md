# MetroPulse

NYC Yellow Taxi analytics and demand forecasting project. Currently includes a downloader, data profiler, and React starter page. The database, API, forecasts, and dashboard are still to be built.

## Setup

Requires uv and Node.js 22.12+.

```bash
uv sync --locked
npm --prefix frontend ci
npm --prefix frontend run dev
```

Open http://localhost:5173.

## Data

Source: [NYC TLC trip records](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page). Initial scope: January–March 2025.

```bash
uv run python -m ingestion.download --year 2025 --month 1 --taxi-type yellow
make profile
```

Use `--month 2` or `--month 3` for the other months. Verified downloads are skipped; `--force` refreshes them. Raw data and generated profiles are Git-ignored.

Optional settings are listed in `.env.example`; export them in your shell or use CLI flags. The downloader does not automatically load `.env`.

## Checks

```bash
make check
```
