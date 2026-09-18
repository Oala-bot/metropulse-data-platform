{{ config(indexes=[{'columns': ['pickup_hour', 'pickup_zone_id'], 'unique': true}]) }}
select
    pickup_hour, pickup_zone_id,
    count(*) as trip_count,
    sum(total_amount) as total_revenue,
    sum(fare_amount) as total_fare,
    sum(trip_distance) as total_distance,
    sum(duration_seconds) as total_duration_seconds
from {{ ref('fact_trip') }}
group by pickup_hour, pickup_zone_id
