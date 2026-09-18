{{ config(indexes=[{'columns': ['zone_id'], 'unique': true}]) }}
select location_id as zone_id, borough, zone as zone_name, service_zone
from {{ ref('stg_zone') }}
