select
    series_code,
    observation_date,
    value
from {{ ref('fct_economic_observations') }}
where
    (indicator_key = 'selic_target' and value not between 0 and 50)
    or (indicator_key = 'ipca_monthly' and value not between -5 and 10)
    or (indicator_key = 'usd_brl' and value not between 0 and 20)
    or (indicator_key = 'unemployment' and value not between 0 and 30)
