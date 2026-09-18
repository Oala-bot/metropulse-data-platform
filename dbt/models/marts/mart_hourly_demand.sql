{{ config(materialized='view') }}
select
    pickup_hour, pickup_zone_id, trip_count,
    extract(hour from pickup_hour)::integer as hour_of_day,
    extract(isodow from pickup_hour)::integer as day_of_week,
    extract(isodow from pickup_hour) in (6, 7) as is_weekend
from {{ ref('agg_zone_hour') }}
