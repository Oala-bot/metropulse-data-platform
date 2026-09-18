{{ config(indexes=[{'columns': ['date_key'], 'unique': true}]) }}
with bounds as (
    select min(pickup_at)::date as first_date, max(dropoff_at)::date as last_date
    from {{ ref('stg_trip') }}
), dates as (
    select generate_series(first_date::timestamp, last_date::timestamp, interval '1 day')::date as date
    from bounds
)
select
    to_char(date, 'YYYYMMDD')::integer as date_key,
    date,
    extract(year from date)::integer as year,
    extract(month from date)::integer as month,
    extract(day from date)::integer as day,
    extract(isodow from date)::integer as day_of_week,
    extract(isodow from date) in (6, 7) as is_weekend
from dates
