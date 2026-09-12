import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "dbt_dag" / "include"))

from economic_pipeline.snowflake import relation, safe_identifier


def test_relation_normalizes_safe_identifiers():
    assert relation("dbt_db", "raw", "bcb_series") == "DBT_DB.RAW.BCB_SERIES"


def test_identifier_rejects_sql_fragments():
    with pytest.raises(ValueError):
        safe_identifier("RAW; drop schema RAW")
