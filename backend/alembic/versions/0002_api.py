from alembic import op

revision = "0002_api"
down_revision = "0001_ingestion"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE pipeline_run DROP CONSTRAINT pipeline_run_status_check;
        ALTER TABLE pipeline_run ADD CONSTRAINT pipeline_run_status_check
            CHECK (status IN ('queued','running','succeeded','failed'));
        ALTER TABLE pipeline_run ADD COLUMN source_year smallint;
        ALTER TABLE pipeline_run ADD COLUMN source_month smallint
            CHECK (source_month BETWEEN 1 AND 12);
        CREATE INDEX ix_pipeline_run_started ON pipeline_run(started_at DESC);
        CREATE TABLE forecast_zone_hour (
            model_run_id uuid NOT NULL REFERENCES model_run(id),
            pickup_zone_id smallint NOT NULL REFERENCES staging.zone(location_id),
            hour_at timestamp NOT NULL,
            predicted_count double precision NOT NULL CHECK (
                predicted_count >= 0 AND predicted_count < 'Infinity'::double precision
            ),
            created_at timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (model_run_id, pickup_zone_id, hour_at)
        );
        CREATE INDEX ix_forecast_hour ON forecast_zone_hour(hour_at, pickup_zone_id);
    """)


def downgrade() -> None:
    op.execute("""
        DROP TABLE forecast_zone_hour;
        DROP INDEX ix_pipeline_run_started;
        ALTER TABLE pipeline_run DROP COLUMN source_month;
        ALTER TABLE pipeline_run DROP COLUMN source_year;
        UPDATE pipeline_run SET status='failed', finished_at=now()
            WHERE status='queued';
        ALTER TABLE pipeline_run DROP CONSTRAINT pipeline_run_status_check;
        ALTER TABLE pipeline_run ADD CONSTRAINT pipeline_run_status_check
            CHECK (status IN ('running','succeeded','failed'));
    """)
