{{ config(indexes=[{'columns': ['trip_date', 'zone_id', 'direction'], 'unique': true}]) }}
select
    trip_date, pickup_zone_id as zone_id, 'pickup'::text as direction,
    count(*) as trip_count, sum(total_amount) as total_revenue,
    sum(fare_amount) as total_fare, sum(trip_distance) as total_distance,
    sum(duration_seconds) as total_duration_seconds
from {{ ref('fact_trip') }}
group by trip_date, pickup_zone_id
union all
select
    trip_date, dropoff_zone_id as zone_id, 'dropoff'::text as direction,
    count(*) as trip_count, sum(total_amount) as total_revenue,
    sum(fare_amount) as total_fare, sum(trip_distance) as total_distance,
    sum(duration_seconds) as total_duration_seconds
from {{ ref('fact_trip') }}
group by trip_date, dropoff_zone_id
