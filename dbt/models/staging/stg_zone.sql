select * from {{ source('staging', 'zone') }}
