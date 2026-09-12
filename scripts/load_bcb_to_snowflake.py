"""Load BCB series into Snowflake using the local dbt profile credentials."""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date
from pathlib import Path

import snowflake.connector
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "dbt_dag" / "include"))

from economic_pipeline.snowflake import run_incremental_ingestion  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", default="data_pipeline")
    parser.add_argument("--target", default="dev")
    parser.add_argument("--raw-schema", default="RAW")
    parser.add_argument("--end-date", type=date.fromisoformat, default=date.today())
    return parser.parse_args()


def connection_config(profile_name: str, target_name: str) -> dict[str, object]:
    environment = {
        "account": os.getenv("SNOWFLAKE_ACCOUNT"),
        "user": os.getenv("SNOWFLAKE_USER"),
        "password": os.getenv("SNOWFLAKE_PASSWORD"),
        "database": os.getenv("SNOWFLAKE_DATABASE"),
        "warehouse": os.getenv("SNOWFLAKE_WAREHOUSE"),
        "role": os.getenv("SNOWFLAKE_ROLE"),
    }
    if all(environment[key] for key in ("account", "user", "password", "database", "warehouse")):
        return {key: value for key, value in environment.items() if value}

    profiles_path = Path.home() / ".dbt" / "profiles.yml"
    profiles = yaml.safe_load(profiles_path.read_text(encoding="utf-8"))
    target = profiles[profile_name]["outputs"][target_name]
    return {
        key: target[key]
        for key in ("account", "user", "password", "database", "warehouse", "role")
        if target.get(key)
    }


def main() -> None:
    args = parse_args()
    config = connection_config(args.profile, args.target)
    connection = snowflake.connector.connect(**config)
    try:
        summary = run_incremental_ingestion(
            connection,
            database=str(config["database"]),
            schema=args.raw_schema,
            end_date=args.end_date,
        )
    finally:
        connection.close()
    print(summary)


if __name__ == "__main__":
    main()
