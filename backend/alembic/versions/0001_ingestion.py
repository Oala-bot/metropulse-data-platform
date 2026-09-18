from alembic import op

revision = "0001_ingestion"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE load_batch (
            id uuid PRIMARY KEY,
            source_file text NOT NULL,
            source_checksum char(64) NOT NULL,
            source_year smallint NOT NULL,
            source_month smallint NOT NULL CHECK (source_month BETWEEN 1 AND 12),
            started_at timestamptz NOT NULL DEFAULT now(),
            finished_at timestamptz,
            rows_read bigint NOT NULL DEFAULT 0 CHECK (rows_read >= 0),
            rows_accepted bigint NOT NULL DEFAULT 0 CHECK (rows_accepted >= 0),
            rows_rejected bigint NOT NULL DEFAULT 0 CHECK (rows_rejected >= 0),
            duplicate_rows bigint NOT NULL DEFAULT 0 CHECK (duplicate_rows >= 0),
            status text NOT NULL CHECK (status IN ('running','succeeded','failed','skipped')),
            failure_message text,
            quarantine_path text,
            CHECK (status <> 'succeeded' OR
                rows_read = rows_accepted + rows_rejected + duplicate_rows)
        );
        CREATE UNIQUE INDEX uq_load_batch_checksum
            ON load_batch(source_checksum) WHERE status = 'succeeded';
        CREATE INDEX ix_load_batch_started ON load_batch(started_at DESC);

        CREATE TABLE pipeline_run (
            id uuid PRIMARY KEY,
            load_batch_id uuid REFERENCES load_batch(id),
            started_at timestamptz NOT NULL DEFAULT now(),
            finished_at timestamptz,
            status text NOT NULL CHECK (status IN ('running','succeeded','failed')),
            task_states jsonb NOT NULL DEFAULT '{}',
            failure_message text
        );
        CREATE TABLE data_quality_result (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            load_batch_id uuid NOT NULL REFERENCES load_batch(id),
            rule text NOT NULL,
            failed_rows bigint NOT NULL CHECK (failed_rows >= 0),
            checked_at timestamptz NOT NULL DEFAULT now(),
            UNIQUE (load_batch_id, rule)
        );
        CREATE TABLE model_run (
            id uuid PRIMARY KEY,
            model_version text NOT NULL UNIQUE,
            started_at timestamptz NOT NULL DEFAULT now(),
            finished_at timestamptz,
            status text NOT NULL CHECK (status IN ('running','succeeded','failed')),
            training_start timestamp,
            training_end timestamp,
            test_start timestamp,
            test_end timestamp,
            features jsonb NOT NULL DEFAULT '[]',
            metrics jsonb NOT NULL DEFAULT '{}',
            artifact_path text,
            failure_message text
        );
        CREATE SCHEMA staging;
        CREATE TABLE staging.zone (
            location_id smallint PRIMARY KEY,
            borough text NOT NULL,
            zone text NOT NULL,
            service_zone text
        );
        CREATE TABLE staging.trip (
            trip_key char(64) PRIMARY KEY,
            load_batch_id uuid NOT NULL REFERENCES load_batch(id),
            source_row bigint NOT NULL,
            source_year smallint NOT NULL,
            source_month smallint NOT NULL,
            vendor_id smallint NOT NULL,
            pickup_at timestamp NOT NULL,
            dropoff_at timestamp NOT NULL,
            pickup_zone_id smallint NOT NULL REFERENCES staging.zone(location_id),
            dropoff_zone_id smallint NOT NULL REFERENCES staging.zone(location_id),
            payment_type smallint NOT NULL CHECK (payment_type BETWEEN 0 AND 6),
            passenger_count smallint CHECK (passenger_count BETWEEN 0 AND 9),
            rate_code smallint,
            store_and_fwd_flag text,
            trip_distance double precision NOT NULL CHECK (trip_distance BETWEEN 0 AND 1000),
            fare_amount numeric(12,2) NOT NULL CHECK (fare_amount BETWEEN 0 AND 10000),
            extra numeric(12,2) CHECK (extra BETWEEN 0 AND 10000),
            mta_tax numeric(12,2) CHECK (mta_tax BETWEEN 0 AND 10000),
            tip_amount numeric(12,2) CHECK (tip_amount BETWEEN 0 AND 10000),
            tolls_amount numeric(12,2) CHECK (tolls_amount BETWEEN 0 AND 10000),
            improvement_surcharge numeric(12,2) CHECK (improvement_surcharge BETWEEN 0 AND 10000),
            congestion_surcharge numeric(12,2) CHECK (congestion_surcharge BETWEEN 0 AND 10000),
            airport_fee numeric(12,2) CHECK (airport_fee BETWEEN 0 AND 10000),
            cbd_congestion_fee numeric(12,2) CHECK (cbd_congestion_fee BETWEEN 0 AND 10000),
            total_amount numeric(12,2) NOT NULL CHECK (total_amount BETWEEN 0 AND 10000),
            duration_seconds double precision NOT NULL
                CHECK (duration_seconds > 0 AND duration_seconds <= 86400),
            CHECK (pickup_at < dropoff_at)
        );
        CREATE INDEX ix_trip_pickup ON staging.trip(pickup_at);
        CREATE INDEX ix_trip_zone_pickup ON staging.trip(pickup_zone_id, pickup_at);
        CREATE INDEX ix_trip_dropoff ON staging.trip(dropoff_zone_id, dropoff_at);
        CREATE INDEX ix_trip_batch ON staging.trip(load_batch_id);
    """)


def downgrade() -> None:
    op.execute("""
        DROP TABLE staging.trip;
        DROP TABLE staging.zone;
        DROP SCHEMA staging;
        DROP TABLE model_run;
        DROP TABLE data_quality_result;
        DROP TABLE pipeline_run;
        DROP TABLE load_batch;
    """)
