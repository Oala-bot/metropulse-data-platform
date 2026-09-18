from pathlib import Path

import pyarrow.parquet as pq

COLUMN_MAP = {
    "VendorID": "vendor_id",
    "tpep_pickup_datetime": "pickup_at",
    "tpep_dropoff_datetime": "dropoff_at",
    "PULocationID": "pickup_zone_id",
    "DOLocationID": "dropoff_zone_id",
    "payment_type": "payment_type",
    "passenger_count": "passenger_count",
    "RatecodeID": "rate_code",
    "store_and_fwd_flag": "store_and_fwd_flag",
    "trip_distance": "trip_distance",
    "fare_amount": "fare_amount",
    "extra": "extra",
    "mta_tax": "mta_tax",
    "tip_amount": "tip_amount",
    "tolls_amount": "tolls_amount",
    "improvement_surcharge": "improvement_surcharge",
    "congestion_surcharge": "congestion_surcharge",
    "Airport_fee": "airport_fee",
    "cbd_congestion_fee": "cbd_congestion_fee",
    "total_amount": "total_amount",
}
MONEY_COLUMNS = list(COLUMN_MAP.values())[10:]


def validate_schema(path: Path) -> pq.ParquetFile:
    parquet = pq.ParquetFile(path)
    missing = sorted(COLUMN_MAP.keys() - set(parquet.schema_arrow.names))
    if missing:
        raise ValueError(f"Missing required 2025 Yellow Taxi columns: {', '.join(missing)}")
    return parquet
