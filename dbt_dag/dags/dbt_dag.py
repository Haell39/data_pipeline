from datetime import datetime
from pathlib import Path

from cosmos import DbtDag, ProfileConfig, ProjectConfig
from cosmos.profiles import SnowflakeUserPasswordProfileMapping

# O caminho até onde estão suas ferramentas dbt dentro do Docker
dbt_project_path = Path("/usr/local/airflow/dags/dbt/data_pipeline")

# Configuração de conexão que você salvou no Airflow
profile_config = ProfileConfig(
    profile_name="data_pipeline",
    target_name="dev",
    profile_mapping=SnowflakeUserPasswordProfileMapping(
        conn_id="snowflake_conn",
        profile_args={
            "database": "DBT_DB",
            "schema": "DBT_SCHEMA",
        },
    ),
)

# A criação da esteira visual (DAG)
dbt_snowflake_dag = DbtDag(
    project_config=ProjectConfig(dbt_project_path),
    profile_config=profile_config,
    dag_id="dbt_dag",
    schedule="@daily",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    default_args={"retries": 2},
    tags=["dbt", "snowflake"],
)
