import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import pandas as pd

from ingestion.validate import COLUMN_MAP, MONEY_COLUMNS


@dataclass
class CleanBatch:
    accepted: pd.DataFrame
    rejected: pd.DataFrame
    rule_counts: dict[str, int]


def trip_key(values: tuple[Any, ...]) -> str:
    normalized: list[str | None] = []
    for value in values:
        if pd.isna(value):
            normalized.append(None)
        elif isinstance(value, (datetime, pd.Timestamp)):
            normalized.append(value.isoformat(timespec="microseconds"))
        elif isinstance(value, (int, float)):
            normalized.append(format(float(value) if value else 0.0, ".17g"))
        else:
            normalized.append(str(value))
    encoded = json.dumps(normalized, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode()).hexdigest()


def clean_batch(
    raw: pd.DataFrame, zone_ids: set[int], year: int, month: int, offset: int = 0
) -> CleanBatch:
    raw = raw.reset_index(drop=True).copy()
    raw["source_row"] = range(offset + 1, offset + len(raw) + 1)
    frame = raw.rename(columns=COLUMN_MAP).copy()
    rules: dict[str, pd.Series[bool]] = {}
    required = [
        "vendor_id",
        "pickup_at",
        "dropoff_at",
        "pickup_zone_id",
        "dropoff_zone_id",
        "payment_type",
        "trip_distance",
        "fare_amount",
        "total_amount",
    ]
    rules["missing_required_value"] = frame[required].isna().any(axis=1)
    for column in ["pickup_at", "dropoff_at"]:
        frame[column] = pd.to_datetime(frame[column], errors="coerce")
        if frame[column].dt.tz is not None:
            raise ValueError("TLC timestamps must be timezone-naive New York local times")
        rules[f"invalid_{column}"] = frame[column].isna()
    numeric = [
        "vendor_id",
        "pickup_zone_id",
        "dropoff_zone_id",
        "payment_type",
        "passenger_count",
        "rate_code",
        "trip_distance",
        *MONEY_COLUMNS,
    ]
    for column in numeric:
        original = frame[column]
        frame[column] = pd.to_numeric(original, errors="coerce")
        rules[f"invalid_number_{column}"] = original.notna() & frame[column].isna()
    for column in ["pickup_zone_id", "dropoff_zone_id"]:
        rules[f"unknown_{column}"] = ~frame[column].isin(zone_ids)
    rules["invalid_vendor"] = ~frame["vendor_id"].between(1, 32767) | (frame["vendor_id"] % 1 != 0)
    rules["invalid_payment_type"] = ~frame["payment_type"].isin(range(0, 7))
    for column, upper in [("passenger_count", 9), ("rate_code", 32767)]:
        rules[f"invalid_{column}"] = frame[column].notna() & (
            ~frame[column].between(0, upper) | (frame[column] % 1 != 0)
        )
    rules["invalid_store_and_fwd_flag"] = frame["store_and_fwd_flag"].notna() & ~frame[
        "store_and_fwd_flag"
    ].isin(["Y", "N"])
    rules["invalid_distance"] = ~frame["trip_distance"].between(0, 1000)
    for column in MONEY_COLUMNS:
        rules[f"invalid_{column}"] = frame[column].notna() & ~frame[column].between(0, 10000)
    frame["duration_seconds"] = (frame["dropoff_at"] - frame["pickup_at"]).dt.total_seconds()
    rules["invalid_duration"] = ~frame["duration_seconds"].between(0, 86400, inclusive="right")
    start = pd.Timestamp(year=year, month=month, day=1)
    rules["pickup_outside_month"] = ~frame["pickup_at"].between(
        start, start + pd.offsets.MonthBegin(1), inclusive="left"
    )
    flags = pd.DataFrame(rules).fillna(True)
    rejected_mask = flags.any(axis=1)
    rejected = raw.loc[rejected_mask].copy()
    rejected["rejection_reasons"] = [
        [name for name, failed in zip(flags.columns, values, strict=True) if failed]
        for values in flags.loc[rejected_mask].itertuples(index=False, name=None)
    ]
    accepted = frame.loc[
        ~rejected_mask, [*COLUMN_MAP.values(), "duration_seconds", "source_row"]
    ].copy()
    # The key excludes load metadata. Identical legitimate trips can still share this key.
    accepted["trip_key"] = [
        trip_key(values)
        for values in accepted[list(COLUMN_MAP.values())].itertuples(index=False, name=None)
    ]
    return CleanBatch(accepted, rejected, {name: int(mask.sum()) for name, mask in rules.items()})
