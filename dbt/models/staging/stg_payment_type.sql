select payment_type::smallint, payment_name
from {{ ref('payment_types') }}
