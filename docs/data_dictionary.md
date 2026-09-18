# Source data dictionary — Milestone 1

See `january-2025-profile.json` for observed Arrow types and full null/range counts. Source semantics come from the [TLC Yellow Taxi dictionary](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page). Downstream dimensional fields will be documented with their implementation.

| Fields | Meaning |
| --- | --- |
| VendorID | Reporting technology provider |
| tpep_pickup_datetime / tpep_dropoff_datetime | Source local pickup/drop-off timestamps; no timezone in Parquet |
| PULocationID / DOLocationID | TLC taxi-zone identifiers |
| passenger_count | Reported passenger count; nullable |
| trip_distance | Reported miles |
| RatecodeID | Rate category |
| store_and_fwd_flag | Whether the record was stored before transmission |
| payment_type | Payment category code |
| fare_amount | Metered fare |
| extra / mta_tax | Extras and MTA tax |
| tip_amount / tolls_amount | Recorded tips and tolls |
| improvement_surcharge / congestion_surcharge | Surcharges |
| Airport_fee | Airport fee, preserving source capitalization |
| cbd_congestion_fee | Central business district congestion fee added for 2025 |
| total_amount | Recorded total charge |

Do not equate missing passenger counts with zero. Preserve source values for auditability. Negative fares can represent reversals or other source behavior: future cleaning will quarantine according to documented project policy rather than silently remove them. Date boundaries and daylight-saving handling will need an explicit warehouse policy.
