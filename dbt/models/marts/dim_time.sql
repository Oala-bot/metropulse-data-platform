{{ config(indexes=[{'columns': ['time_key'], 'unique': true}]) }}
select minute_of_day as time_key, minute_of_day / 60 as hour, minute_of_day % 60 as minute
from generate_series(0, 1439) as minute_of_day
