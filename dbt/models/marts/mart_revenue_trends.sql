{{ config(indexes=[{'columns': ['trip_date', 'pickup_zone_id'], 'unique': true}]) }}
select
    trip_date, pickup_zone_id, count(*) as trip_count,
    sum(fare_amount) as fare_amount, sum(tip_amount) as tip_amount,
    sum(tolls_amount) as tolls_amount, sum(extra) as extra,
    sum(mta_tax) as mta_tax, sum(improvement_surcharge) as improvement_surcharge,
    sum(congestion_surcharge) as congestion_surcharge,
    sum(airport_fee) as airport_fee, sum(cbd_congestion_fee) as cbd_congestion_fee,
    sum(total_amount) as total_revenue
from {{ ref('fact_trip') }}
group by trip_date, pickup_zone_id
