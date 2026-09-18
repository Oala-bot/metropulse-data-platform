# Data storage

Source: https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page

Target months: January, February, March 2025, Yellow Taxi. TLC receives provider-submitted records and does not guarantee their accuracy. The 2025 schema adds `cbd_congestion_fee`.

`raw/`, `rejected/`, and `processed/` are ignored by Git. Never commit downloaded monthly Parquet files. Download sidecars contain SHA-256, source URL, bytes, and elapsed seconds.

`sample/trips.csv` is a tiny hand-authored deterministic fixture, not an extract or a representative statistical sample. It includes an invalid negative distance and a duplicate for later cleaning tests. Routine tests do not access the network.
