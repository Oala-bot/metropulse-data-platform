select
    t.*,
    pickup_at::date as trip_date,
    to_char(pickup_at, 'YYYYMMDD')::integer as pickup_date_key,
    to_char(dropoff_at, 'YYYYMMDD')::integer as dropoff_date_key,
    (extract(hour from pickup_at)::integer * 60 + extract(minute from pickup_at)::integer) as pickup_time_key,
    (extract(hour from dropoff_at)::integer * 60 + extract(minute from dropoff_at)::integer) as dropoff_time_key,
    date_trunc('hour', pickup_at) as pickup_hour
from {{ ref('stg_trip') }} t
