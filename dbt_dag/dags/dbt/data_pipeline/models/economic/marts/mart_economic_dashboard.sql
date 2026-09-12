with monthly_metrics as (
    select
        month,
        max(case when indicator_key = 'selic_target' then end_of_period_value end) as selic_target,
        max(case when indicator_key = 'ipca_monthly' then end_of_period_value end) as ipca_monthly,
        max(case when indicator_key = 'usd_brl' then end_of_period_value end) as usd_brl,
        max(case when indicator_key = 'unemployment' then end_of_period_value end) as unemployment_rate,
        max(loaded_at) as loaded_at
    from {{ ref('mart_economic_monthly') }}
    group by month
),

with_ipca_window as (
    select
        *,
        count(ipca_monthly) over (
            order by month rows between 11 preceding and current row
        ) as ipca_month_count,
        exp(
            sum(ln(1 + ipca_monthly / 100)) over (
                order by month rows between 11 preceding and current row
            )
        ) * 100 - 100 as ipca_12m
    from monthly_metrics
)

select
    month,
    selic_target,
    ipca_monthly,
    case when ipca_month_count = 12 then ipca_12m end as ipca_12m,
    usd_brl,
    unemployment_rate,
    selic_target - case when ipca_month_count = 12 then ipca_12m end as nominal_real_rate_spread,
    loaded_at
from with_ipca_window
