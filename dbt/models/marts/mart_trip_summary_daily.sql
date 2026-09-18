{{ config(indexes=[{'columns': ['trip_date', 'pickup_zone_id'], 'unique': true}]) }}
select
    pickup_hour::date as trip_date, pickup_zone_id,
    sum(trip_count)::bigint as trip_count,
    sum(total_revenue) as total_revenue,
    sum(total_fare) as total_fare,
    sum(total_distance) as total_distance,
    sum(total_duration_seconds) as total_duration_seconds
from {{ ref('agg_zone_hour') }}
group by pickup_hour::date, pickup_zone_id
