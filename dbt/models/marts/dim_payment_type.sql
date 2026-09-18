{{ config(indexes=[{'columns': ['payment_type'], 'unique': true}]) }}
select * from {{ ref('stg_payment_type') }}
