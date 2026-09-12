select
    series_code::integer as series_code,
    observation_date::date as observation_date,
    value::number(18, 6) as value,
    source_url::varchar as source_url,
    loaded_at::timestamp_tz as loaded_at,
    batch_id::varchar as batch_id
from {{ source('bcb_raw', 'bcb_series') }}
