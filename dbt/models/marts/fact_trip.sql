{{ config(indexes=[
    {'columns': ['trip_key'], 'unique': true},
    {'columns': ['pickup_at']},
    {'columns': ['pickup_zone_id', 'pickup_at']},
    {'columns': ['dropoff_zone_id', 'pickup_at']},
    {'columns': ['pickup_hour']}
]) }}
select * from {{ ref('int_trip_enriched') }}
