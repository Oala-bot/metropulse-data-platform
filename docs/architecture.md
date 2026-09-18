# Architecture and milestone boundaries

MetroPulse is one repository and one evolving local platform. January–March 2025 Yellow Taxi data is the initial scope. Historical trip records are downloaded from official TLC storage. Future stages validate and quarantine rows, load staging, transform into dimensional analytics, and train hourly zone demand models. A read-only public API feeds the dashboard, with a separately protected ingestion trigger.

## Current implementation

`ingestion/download.py` owns transport integrity and a CLI. Each month is streamed to a unique same-directory temporary file. SHA-256 is computed while streaming; content length is checked when provided. A successful transfer replaces its destination, then writes a manifest. Local checksum and source checks make repeat invocation skip safely. Transport errors and transient HTTP responses retry exponentially; permanent HTTP errors do not.

`ingestion/profile.py` reads every row in 65,536-row Arrow batches to measure null counts, ranges, negative financial values, and reversed/zero-duration timestamps. It reports source observations without changing the raw data.

`frontend/` contains a responsive accessible foundation page and local development/build/test tooling. It has no API dependencies or fabricated metrics.

## Planned storage ownership

Alembic will manage staging and operational tables: load_batch, pipeline_run, data_quality_result, model_run, and forecast persistence. dbt will manage fact_trip, dim_zone, dim_date, dim_time, dim_payment_type, agg_zone_hour, and the requested analytics marts. Operational schema changes and analytical transformations must not compete for table ownership.

Stable generated trip keys will enforce rerun safety, with collision/identical-legitimate-trip limitations documented when the key is implemented. Pipeline task payloads will contain paths and IDs, not entire dataframes. Publication must wait for quality and dbt checks.

## Forecasting boundary

Hourly pickup-zone demand will have a weekly seasonal baseline, lag/rolling features calculated strictly from prior observations, chronological splits, and measured MAE/RMSE. Multi-hour forecasting must use recursively available predictions or a documented direct strategy; test-period actuals cannot silently become future inputs. No forecasting implementation exists yet.

## Development and security

Use feature branches, tested milestone commits, locked dependencies, and VS Code settings. Raw data, credentials, caches, model binaries, logs, and build output are excluded. No accounts, cloud infrastructure, Kafka, Spark, or Kubernetes are in scope. Docker Compose will be added when it can start actual tested services.
