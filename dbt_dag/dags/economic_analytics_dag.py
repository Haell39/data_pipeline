from datetime import date
from pathlib import Path
import sys

import pendulum
from airflow.sdk import dag, task
from cosmos import DbtTaskGroup, ProfileConfig, ProjectConfig, RenderConfig
from cosmos.profiles import SnowflakeUserPasswordProfileMapping

AIRFLOW_HOME = Path("/usr/local/airflow")
DBT_PROJECT_PATH = AIRFLOW_HOME / "dags" / "dbt" / "data_pipeline"
INCLUDE_PATH = AIRFLOW_HOME / "include"
if str(INCLUDE_PATH) not in sys.path:
    sys.path.insert(0, str(INCLUDE_PATH))

profile_config = ProfileConfig(
    profile_name="data_pipeline",
    target_name="dev",
    profile_mapping=SnowflakeUserPasswordProfileMapping(
        conn_id="snowflake_conn",
        profile_args={"database": "DBT_DB", "schema": "DBT_SCHEMA"},
    ),
)


@dag(
    dag_id="economic_analytics_pipeline",
    schedule="0 6 * * *",
    start_date=pendulum.datetime(2026, 1, 1, tz="America/Recife"),
    catchup=False,
    default_args={"retries": 2},
    tags=["economic-data", "bcb", "dbt", "snowflake"],
    doc_md="""
    ## Pulso Econômico Brasil

    Carga incremental e idempotente das séries SGS/BCB seguida da construção e
    validação dos marts consumidos pela aplicação Streamlit.
    """,
)
def economic_analytics_pipeline():
    @task(task_id="ingest_bcb_series")
    def ingest_bcb_series() -> dict[str, object]:
        from airflow.providers.snowflake.hooks.snowflake import SnowflakeHook
        from economic_pipeline.snowflake import run_incremental_ingestion

        hook = SnowflakeHook(snowflake_conn_id="snowflake_conn")
        connection = hook.get_conn()
        try:
            return run_incremental_ingestion(
                connection,
                database="DBT_DB",
                schema="RAW",
                bootstrap_start=date(2020, 1, 1),
            )
        finally:
            connection.close()

    ingestion = ingest_bcb_series()

    transformations = DbtTaskGroup(
        group_id="transform_economic_models",
        project_config=ProjectConfig(DBT_PROJECT_PATH),
        profile_config=profile_config,
        render_config=RenderConfig(select=["+tag:economic"]),
        operator_args={"install_deps": True},
    )

    ingestion >> transformations


economic_analytics_pipeline()
