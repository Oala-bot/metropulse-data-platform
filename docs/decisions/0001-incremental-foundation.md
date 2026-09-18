# ADR 0001: Establish a verifiable foundation before adding services

Status: accepted.

Use Python 3.12 with uv, React/TypeScript with Vite, and CSS Modules. Add the remaining agreed dependencies when their milestones need them. This avoids a misleading scaffold that appears to run an unimplemented system. Docker Compose is deliberately deferred until working services exist; VS Code future-service tasks are explicitly labeled.

The downloader supports Yellow Taxi only. A SHA-256 sidecar records local integrity, source URL, byte count, and timing. Verified local files are skipped; `--force` refreshes possible upstream revisions. SHA-256 is not proof of authenticity because TLC does not supply a reference digest. HTTPS establishes transport trust. Retries apply to transport errors, HTTP 408/429, and 5xx. Permanent errors fail immediately.

Download and manifest writes each use same-directory atomic replacement. An interrupted manifest write causes a safe download on the next invocation. Concurrent writers to the same month are not supported; orchestration will serialize them. Schema and row validation belong to Milestone 2, not the transport layer.

Use the repository owner's GitHub name and noreply email locally; do not alter global Git identity. The initial tested feature commit seeds main because the remote is empty. Later changes use feature branches from main.
