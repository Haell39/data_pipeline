{{
    config(
        materialized='incremental',
        unique_key='observation_key',
        incremental_strategy='merge',
        on_schema_change='fail'
    )
}}

select
    {{ dbt_utils.generate_surrogate_key([
        'observations.series_code',
        'observations.observation_date'
    ]) }} as observation_key,
    observations.series_code,
    indicators.indicator_key,
    observations.observation_date,
    observations.value,
    observations.source_url,
    observations.loaded_at,
    observations.batch_id
from {{ ref('stg_bcb_observations') }} as observations
inner join {{ ref('dim_economic_indicator') }} as indicators
    on observations.series_code = indicators.series_code
{% if is_incremental() %}
where observations.loaded_at >= (
    select coalesce(dateadd(day, -1, max(loaded_at)), '1900-01-01'::timestamp_tz)
    from {{ this }}
)
{% endif %}
