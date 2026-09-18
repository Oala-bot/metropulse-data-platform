{{ config(indexes=[{'columns': ['trip_date', 'pickup_zone_id', 'payment_type'], 'unique': true}]) }}
select
    trip_date, pickup_zone_id, payment_type, count(*) as trip_count,
    sum(total_amount) as total_revenue, sum(fare_amount) as total_fare
from {{ ref('fact_trip') }}
group by trip_date, pickup_zone_id, payment_type
