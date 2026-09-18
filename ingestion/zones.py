import csv
import os
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

import httpx

ZONE_URL = "https://d37ci6vzurychx.cloudfront.net/misc/taxi_zone_lookup.csv"


@dataclass(frozen=True)
class Zone:
    location_id: int
    borough: str
    zone: str
    service_zone: str | None


def read_zones(path: Path) -> list[Zone]:
    with path.open(newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        required = {"LocationID", "Borough", "Zone", "service_zone"}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError("Zone lookup is missing required columns")
        zones = [
            Zone(int(row["LocationID"]), row["Borough"], row["Zone"], row["service_zone"] or None)
            for row in reader
        ]
    ids = {zone.location_id for zone in zones}
    if not zones or len(ids) != len(zones) or any(not 1 <= number <= 32767 for number in ids):
        raise ValueError("Zone lookup must contain unique, valid location IDs")
    return zones


def download_zones(path: Path) -> list[Zone]:
    if path.exists():
        return read_zones(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=30, follow_redirects=True) as client:
        for attempt in range(3):
            temporary: Path | None = None
            try:
                response = client.get(ZONE_URL)
                response.raise_for_status()
                with tempfile.NamedTemporaryFile(
                    dir=path.parent, suffix=".part", delete=False
                ) as f:
                    temporary = Path(f.name)
                    f.write(response.content)
                zones = read_zones(temporary)
                os.replace(temporary, path)
                return zones
            except (httpx.TransportError, httpx.HTTPStatusError) as exc:
                permanent = isinstance(exc, httpx.HTTPStatusError) and (
                    exc.response.status_code < 500 and exc.response.status_code not in {408, 429}
                )
                if permanent or attempt == 2:
                    raise
                time.sleep(2**attempt)
            finally:
                if temporary:
                    temporary.unlink(missing_ok=True)
    raise RuntimeError("Zone download failed")
