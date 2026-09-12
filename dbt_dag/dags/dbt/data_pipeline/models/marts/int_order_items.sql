select
    line_item.order_item_key,
    line_item.order_key,
    line_item.line_number,
    line_item.extended_price,
    line_item.discount_percentage,
    {{ discounted_amount('line_item.extended_price', 'line_item.discount_percentage') }} as item_discount_amount,
    orders.customer_key,
    orders.status_code,
    orders.order_date
from {{ ref('stg_tpch_orders') }} as orders
join {{ ref('stg_tpch_line_items') }} as line_item
    on orders.order_key = line_item.order_key
order by orders.order_date