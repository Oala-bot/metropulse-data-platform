import argparse
import hashlib
import json
import logging
import os
import tempfile
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

LOGGER = logging.getLogger(__name__)
BASE_URL = "https://d37ci6vzurychx.cloudfront.net/trip-data"
CHUNK_SIZE = 1024 * 1024


@dataclass(frozen=True)
class DownloadResult:
    source: str
    destination: str
    byte_count: int
    checksum: str
    elapsed_seconds: float
    skipped: bool


def source_url(year: int, month: int, taxi_type: str = "yellow", base_url: str = BASE_URL) -> str:
    if not 2009 <= year <= datetime.now(UTC).year:
        raise ValueError("year must be between 2009 and the current year")
    if not 1 <= month <= 12:
        raise ValueError("month must be between 1 and 12")
    if taxi_type != "yellow":
        raise ValueError("only yellow taxi data is supported by this project")
    url = httpx.URL(base_url)
    if url.scheme != "https" or not url.host or url.query or url.fragment or url.userinfo:
        raise ValueError("base URL must be an HTTPS URL without credentials, query, or fragment")
    return f"{base_url.rstrip('/')}/{taxi_type}_tripdata_{year:04d}-{month:02d}.parquet"


def checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(CHUNK_SIZE), b""):
            digest.update(block)
    return digest.hexdigest()


def _matching_manifest(path: Path, source: str) -> dict[str, Any] | None:
    try:
        record = json.loads(path.with_suffix(".parquet.json").read_text())
        if (
            isinstance(record, dict)
            and record.get("source") == source
            and record.get("byte_count") == path.stat().st_size
            and record.get("checksum") == checksum(path)
        ):
            return record
    except (OSError, ValueError):
        pass
    return None


def _save_manifest(path: Path, result: DownloadResult) -> None:
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", dir=path.parent, suffix=".part", delete=False
        ) as f:
            temporary = Path(f.name)
            json.dump(asdict(result), f, indent=2)
            f.write("\n")
        temporary.replace(path.with_suffix(".parquet.json"))
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)


def download(
    year: int,
    month: int,
    taxi_type: str = "yellow",
    output_dir: Path = Path("data/raw"),
    *,
    force: bool = False,
    base_url: str = BASE_URL,
    attempts: int = 3,
    backoff_seconds: float = 1.0,
    client: httpx.Client | None = None,
) -> DownloadResult:
    # Same-month downloads must be serialized by the caller.
    source = source_url(year, month, taxi_type, base_url)
    if attempts < 1 or backoff_seconds < 0:
        raise ValueError("attempts must be positive and backoff_seconds nonnegative")
    start = time.monotonic()
    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / f"{taxi_type}_tripdata_{year:04d}-{month:02d}.parquet"
    # Local checksums cannot detect upstream revisions; use --force to refresh.
    existing = None if force else _matching_manifest(destination, source)
    if existing:
        result = DownloadResult(
            source,
            str(destination),
            destination.stat().st_size,
            str(existing["checksum"]),
            round(time.monotonic() - start, 3),
            True,
        )
        LOGGER.info(json.dumps(asdict(result)))
        return result
    owns_client = client is None
    session = client or httpx.Client(
        timeout=httpx.Timeout(60.0, connect=15.0), follow_redirects=True
    )
    try:
        for attempt in range(attempts):
            temporary: Path | None = None
            try:
                digest = hashlib.sha256()
                byte_count = 0
                with session.stream(
                    "GET", source, headers={"Accept-Encoding": "identity"}
                ) as response:
                    response.raise_for_status()
                    with tempfile.NamedTemporaryFile(
                        dir=output_dir, suffix=".part", delete=False
                    ) as f:
                        temporary = Path(f.name)
                        for block in response.iter_bytes(CHUNK_SIZE):
                            f.write(block)
                            digest.update(block)
                            byte_count += len(block)
                    length = response.headers.get("content-length")
                    if byte_count == 0 or (length is not None and byte_count != int(length)):
                        raise httpx.ReadError(
                            "empty or incomplete response", request=response.request
                        )
                temporary.replace(destination)
                result = DownloadResult(
                    source,
                    str(destination),
                    byte_count,
                    digest.hexdigest(),
                    round(time.monotonic() - start, 3),
                    False,
                )
                _save_manifest(destination, result)
                LOGGER.info(json.dumps(asdict(result)))
                return result
            except (httpx.TransportError, httpx.HTTPStatusError) as exc:
                transient = not isinstance(exc, httpx.HTTPStatusError) or (
                    exc.response.status_code in {408, 429} or exc.response.status_code >= 500
                )
                if not transient or attempt == attempts - 1:
                    raise
                LOGGER.warning("download retry %s/%s: %s", attempt + 1, attempts, exc)
                time.sleep(backoff_seconds * 2**attempt)
            finally:
                if temporary:
                    temporary.unlink(missing_ok=True)
    finally:
        if owns_client:
            session.close()
    raise RuntimeError("download exhausted attempts")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Download NYC TLC Yellow Taxi records.")
    parser.add_argument("--year", required=True, type=int)
    parser.add_argument("--month", required=True, type=int)
    parser.add_argument("--taxi-type", default="yellow")
    parser.add_argument(
        "--output-dir", type=Path, default=Path(os.getenv("RAW_DATA_DIR", "data/raw"))
    )
    parser.add_argument("--base-url", default=os.getenv("TLC_BASE_URL", BASE_URL))
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        download(
            args.year,
            args.month,
            args.taxi_type,
            args.output_dir,
            force=args.force,
            base_url=args.base_url,
        )
    except (ValueError, OSError, httpx.HTTPError) as exc:
        LOGGER.error("download failed: %s", exc)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
