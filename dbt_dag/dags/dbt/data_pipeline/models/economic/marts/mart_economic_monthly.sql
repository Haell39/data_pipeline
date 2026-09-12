with enriched as (
    select
        date_trunc('month', observations.observation_date)::date as month,
        observations.series_code,
        indicators.indicator_key,
        indicators.indicator_name,
        indicators.category,
        indicators.unit,
        indicators.frequency,
        observations.observation_date,
        observations.value,
        observations.loaded_at,
        row_number() over (
            partition by observations.series_code, date_trunc('month', observations.observation_date)
            order by observations.observation_date desc
        ) as latest_in_month
    from {{ ref('fct_economic_observations') }} as observations
    inner join {{ ref('dim_economic_indicator') }} as indicators
        on observations.series_code = indicators.series_code
)

select
    month,
    series_code,
    indicator_key,
    indicator_name,
    category,
    unit,
    frequency,
    max(case when latest_in_month = 1 then value end) as end_of_period_value,
    avg(value) as monthly_average,
    count(*) as observation_count,
    max(observation_date) as last_observation_date,
    max(loaded_at) as loaded_at
from enriched
group by
    month,
    series_code,
    indicator_key,
    indicator_name,
    category,
    unit,
    frequency
