from datetime import datetime
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from ingestion.profile import profile


def test_profile_counts_raw_anomalies(tmp_path: Path) -> None:
    path = tmp_path / "fixture.parquet"
    pq.write_table(
        pa.table(
            {
                "tpep_pickup_datetime": [datetime(2025, 1, 1), datetime(2025, 1, 2)],
                "tpep_dropoff_datetime": [datetime(2025, 1, 1, 1), datetime(2025, 1, 1)],
                "trip_distance": [2.0, -1.0],
                "fare_amount": [10.0, None],
                "total_amount": [15.0, -5.0],
            }
        ),
        path,
    )
    report = profile(path)
    assert report["rows"] == 2
    assert report["negative_counts"]["trip_distance"] == 1
    assert report["pickup_not_before_dropoff"] == 1
    assert report["null_counts"]["fare_amount"] == 1
    assert report["ranges"]["trip_distance"] == {"min": -1.0, "max": 2.0}
