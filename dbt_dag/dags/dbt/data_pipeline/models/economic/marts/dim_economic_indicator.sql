select
    series_code::integer as series_code,
    indicator_key::varchar as indicator_key,
    indicator_name::varchar as indicator_name,
    category::varchar as category,
    unit::varchar as unit,
    frequency::varchar as frequency,
    aggregation::varchar as aggregation,
    display_order::integer as display_order
from {{ ref('economic_series') }}
