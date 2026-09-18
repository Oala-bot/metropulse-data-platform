# Milestone 1 handoff

## Delivered

- Python/uv project with a Python 3.12 pin and dependency lock.
- React/TypeScript/Vite foundation with CSS Modules, frontend lockfile, lint/type/test/build commands.
- VS Code extensions, formatting, type checking, tasks, and debug configurations.
- Git exclusions, environment example, MIT license, pull-request template, Makefile, and documentation.
- Streaming Yellow Taxi downloader: parameter validation, bounded retries, timeouts, temporary files, SHA-256, manifest-based skipping, force refresh, structured result logs, and failing exit status.
- Full-file Arrow profiling and a hand-authored small CSV fixture.
- Future backend, dbt, Airflow, and ML directories contain status documentation only.

## Commands and results

The environment initially lacked uv and Python 3.12. Bootstrap commands from the chat workspace were `python3 -m venv work/tooling` and `work/tooling/bin/pip install uv`. Inside the cloned repository, `UV_PYTHON_INSTALL_DIR=../python UV_CACHE_DIR=../uv-cache ../tooling/bin/uv sync` installed managed Python 3.12 and locked dependencies. A second run with `--locked` passed. Normal developer setup remains `uv sync --locked`.

Exact Python verification commands from the repository root:

```bash
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/mypy
.venv/bin/python -m pytest --cov=ingestion --cov-report=term-missing
.venv/bin/python -m ingestion.download --year 2025 --month 1 --taxi-type yellow
.venv/bin/python -m ingestion.profile data/raw/yellow_tripdata_2025-01.parquet --output docs/january-2025-profile.json
.venv/bin/python -m ingestion.download --year 2025 --month 1 --taxi-type yellow
```

Results: Ruff and formatting pass; strict mypy passes; **20 tests pass**, **92% overall Python coverage**, **98% downloader coverage**. Real download: 59,158,238 bytes in 6.666 seconds. The repeat invocation verified the checksum and skipped in 0.023 seconds. Full-file profile: 3,475,226 rows. Timing is one local observation, not a performance benchmark.

Exact frontend checks:

```bash
npm --prefix frontend ci --cache ../npm-cache
npm --prefix frontend run lint
npm --prefix frontend run format:check
npm --prefix frontend run typecheck
npm --prefix frontend test
npm --prefix frontend run build
npm --prefix frontend run dev
```

Results: locked install, ESLint, Prettier, TypeScript, **1 component test**, and production build pass. Browser inspection at localhost:5173 confirmed the rendered page and its explicit foundation status. The repository was opened with `code .`.

During dependency setup, npm 10 hit a peer-resolution bug while upgrading Vitest. `npm exec --yes --package=npm@11 --cache ../npm-cache -- npm install --prefix frontend --cache ../npm-cache` generated the lock successfully; normal npm 10 `ci` subsequently passed. Vitest 4.1.11 resolves the audit issue encountered in version 3. Current npm audit reports **0 vulnerabilities**. ESLint 9 and a transitive jsdom encoding package emit deprecation notices; they do not prevent checks from passing.

## Source observations

See `january-2025-profile.json` and the README. Negative fares, missing passenger counts, extreme outliers, and timestamps outside the nominal month need documented policies in Milestone 2. Counts are raw observations, not quarantine results. Raw Parquet and its manifest remain ignored, not committed.

## Git

Feature branch: `feature/project-foundation`.
Commit subject: `feat: establish project foundation and tested TLC downloader`.
The same initial tested commit seeds `main`, since the remote began empty. No history is rewritten. Use `git log -1` to obtain the commit ID; the final handoff also links it.

## Known limitations and next step

Docker Desktop is absent. No PostgreSQL loading, dbt transformation, API, forecasts, Airflow, Compose, or CI workflow exists yet. Reserved service tasks cannot run until their milestones. The downloader assumes serialized calls for a given month and verifies local integrity rather than upstream immutability. PyArrow emitted sandbox CPU-detection warnings but completed profiling and tests successfully.

Next: Milestone 2 — schema validation, explicit cleaning rules, quarantine reasons, load-batch auditing, Alembic migrations, and idempotent PostgreSQL staging. Docker Desktop is needed to test PostgreSQL locally.
