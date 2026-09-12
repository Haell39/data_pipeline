select *
from {{ ref('fct_orders') }}
where cast(order_date as date) > current_date
   or cast(order_date as date) < '1990-01-01'