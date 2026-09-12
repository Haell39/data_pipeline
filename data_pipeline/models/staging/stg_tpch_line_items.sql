select
    {{dbt_utils.generate_surrogate_key([
        'l_orderkey',
        'l_linenumber'
    ])
    }} as order_item_key,

    l_orderkey as order_key,
    l_linenumber as line_number,
    l_extendedprice as extended_price,
    l_discount as discount_percentage
from {{source('tpch', 'lineitem')}}