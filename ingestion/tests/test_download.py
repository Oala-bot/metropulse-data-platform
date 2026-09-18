"""Deterministic network-free tests of download integrity and failure semantics."""

import hashlib
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest

from ingestion.download import download, main, source_url


def test_url() -> None:
    assert source_url(2025, 1).endswith("/yellow_tripdata_2025-01.parquet")


@pytest.mark.parametrize(
    "year,month,taxi",
    [
        (2008, 1, "yellow"),
        (9999, 1, "yellow"),
        (2025, 0, "yellow"),
        (2025, 13, "yellow"),
        (2025, 1, "green"),
        (2025, 1, "../yellow"),
    ],
)
def test_invalid_parameters(year: int, month: int, taxi: str) -> None:
    with pytest.raises(ValueError):
        source_url(year, month, taxi)


@pytest.mark.parametrize(
    "url", ["http://example.com", "https://user:pass@example.com", "https://example.com?a=b"]
)
def test_invalid_base_url(url: str) -> None:
    with pytest.raises(ValueError):
        source_url(2025, 1, base_url=url)


def test_download_skip_force_and_corruption(tmp_path: Path) -> None:
    calls = 0
    payload = b"deterministic source bytes" * 1000

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, content=payload)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        first = download(2025, 1, output_dir=tmp_path, client=client)
        assert first.checksum == hashlib.sha256(payload).hexdigest()
        assert first.byte_count == len(payload)
        assert Path(first.destination).read_bytes() == payload
        assert download(2025, 1, output_dir=tmp_path, client=client).skipped
        assert calls == 1
        assert not download(2025, 1, output_dir=tmp_path, client=client, force=True).skipped
        Path(first.destination).write_bytes(b"x" * len(payload))
        assert not download(2025, 1, output_dir=tmp_path, client=client).skipped
        assert calls == 3
        Path(first.destination).with_suffix(".parquet.json").write_text("not json")
        download(2025, 1, output_dir=tmp_path, client=client)
        assert calls == 4
    assert not list(tmp_path.glob("*.part"))


@pytest.mark.parametrize("status", [429, 503])
def test_retry_transient(tmp_path: Path, status: int) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(status if calls == 1 else 200, content=b"data")

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        download(2025, 1, output_dir=tmp_path, client=client, backoff_seconds=0)
    assert calls == 2


def test_404_not_retried(tmp_path: Path) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(404)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(httpx.HTTPStatusError):
            download(2025, 1, output_dir=tmp_path, client=client)
    assert calls == 1
    assert list(tmp_path.iterdir()) == []


class BrokenStream(httpx.SyncByteStream):
    def __iter__(self) -> Iterator[bytes]:
        yield b"partial"
        raise httpx.ReadError("connection interrupted")


def test_partial_failure_preserves_existing_file(tmp_path: Path) -> None:
    destination = tmp_path / "yellow_tripdata_2025-01.parquet"
    destination.write_bytes(b"previous good content")
    with httpx.Client(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, stream=BrokenStream()))
    ) as client:
        with pytest.raises(httpx.ReadError):
            download(
                2025,
                1,
                output_dir=tmp_path,
                client=client,
                force=True,
                attempts=2,
                backoff_seconds=0,
            )
    assert destination.read_bytes() == b"previous good content"
    assert not list(tmp_path.glob("*.part"))


@pytest.mark.parametrize("content,length", [(b"", "0"), (b"short", "100")])
def test_incomplete_response(tmp_path: Path, content: bytes, length: str) -> None:
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, content=content, headers={"content-length": length})
        )
    ) as client:
        with pytest.raises(httpx.ReadError):
            download(2025, 1, output_dir=tmp_path, client=client, attempts=1)
    assert list(tmp_path.iterdir()) == []


def test_cli_invalid_month() -> None:
    assert main(["--year", "2025", "--month", "13"]) == 1


def test_invalid_attempts(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        download(2025, 1, output_dir=tmp_path, attempts=0)
