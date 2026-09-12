"""Idempotent Snowflake loader for normalized BCB observations."""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone
from typing import Iterable, Mapping
from uuid import uuid4

from .bcb import fetch_all_series

IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")


def safe_identifier(value: str) -> str:
    if not IDENTIFIER.fullmatch(value):
        raise ValueError(f"Unsafe Snowflake identifier: {value!r}")
    return value.upper()


def relation(database: str, schema: str, table: str) -> str:
    return ".".join(safe_identifier(part) for part in (database, schema, table))


def ensure_raw_objects(connection, database: str, schema: str = "RAW") -> None:
    raw_table = relation(database, schema, "BCB_SERIES")
    audit_table = relation(database, schema, "PIPELINE_RUNS")
    cursor = connection.cursor()
    try:
        cursor.execute(f"create schema if not exists {safe_identifier(database)}.{safe_identifier(schema)}")
        cursor.execute(
            f"""
            create table if not exists {raw_table} (
                series_code integer not null,
                observation_date date not null,
                value number(18, 6) not null,
                source_url varchar not null,
                loaded_at timestamp_tz not null,
                batch_id varchar not null,
                primary key (series_code, observation_date)
            )
            """
        )
        cursor.execute(
            f"""
            create table if not exists {audit_table} (
                batch_id varchar not null,
                started_at timestamp_tz not null,
                completed_at timestamp_tz,
                status varchar not null,
                rows_extracted integer,
                rows_affected integer,
                range_start date,
                range_end date,
                error_message varchar
            )
            """
        )
    finally:
        cursor.close()


def latest_observation_date(connection, database: str, schema: str = "RAW") -> date | None:
    cursor = connection.cursor()
    try:
        cursor.execute(f"select max(observation_date) from {relation(database, schema, 'BCB_SERIES')}")
        return cursor.fetchone()[0]
    finally:
        cursor.close()


def merge_observations(
    connection,
    rows: Iterable[Mapping[str, object]],
    database: str,
    schema: str = "RAW",
    batch_id: str | None = None,
) -> int:
    normalized_rows = list(rows)
    if not normalized_rows:
        return 0

    current_batch_id = batch_id or str(uuid4())
    raw_table = relation(database, schema, "BCB_SERIES")
    temp_table = relation(
        database,
        schema,
        f"BCB_SERIES_{current_batch_id.replace('-', '_')}",
    )
    cursor = connection.cursor()
    try:
        cursor.execute(f"create temporary table {temp_table} like {raw_table}")
        cursor.executemany(
            f"""
            insert into {temp_table}
                (series_code, observation_date, value, source_url, loaded_at, batch_id)
            values (%s, %s, %s, %s, %s, %s)
            """,
            [
                (
                    row["series_code"],
                    row["observation_date"],
                    row["value"],
                    row["source_url"],
                    row["loaded_at"],
                    current_batch_id,
                )
                for row in normalized_rows
            ],
        )
        cursor.execute(
            f"""
            merge into {raw_table} as target
            using {temp_table} as source
              on target.series_code = source.series_code
             and target.observation_date = source.observation_date
            when matched and target.value <> source.value then update set
                value = source.value,
                source_url = source.source_url,
                loaded_at = source.loaded_at,
                batch_id = source.batch_id
            when not matched then insert
                (series_code, observation_date, value, source_url, loaded_at, batch_id)
            values
                (source.series_code, source.observation_date, source.value,
                 source.source_url, source.loaded_at, source.batch_id)
            """
        )
        return max(cursor.rowcount, 0)
    finally:
        cursor.close()


def run_incremental_ingestion(
    connection,
    database: str,
    schema: str = "RAW",
    bootstrap_start: date = date(2020, 1, 1),
    lookback_days: int = 120,
    end_date: date | None = None,
) -> dict[str, object]:
    """Fetch a bounded lookback and MERGE it, making retries safe."""
    finished_range = end_date or date.today()
    batch_id = str(uuid4())
    started_at = datetime.now(timezone.utc)
    ensure_raw_objects(connection, database, schema)
    maximum_date = latest_observation_date(connection, database, schema)
    range_start = max(bootstrap_start, maximum_date - timedelta(days=lookback_days)) if maximum_date else bootstrap_start
    rows = fetch_all_series(range_start, finished_range)

    audit_table = relation(database, schema, "PIPELINE_RUNS")
    try:
        affected = merge_observations(connection, rows, database, schema, batch_id)
        completed_at = datetime.now(timezone.utc)
        cursor = connection.cursor()
        try:
            cursor.execute(
                f"""
                insert into {audit_table}
                    (batch_id, started_at, completed_at, status, rows_extracted,
                     rows_affected, range_start, range_end, error_message)
                values (%s, %s, %s, 'success', %s, %s, %s, %s, null)
                """,
                (batch_id, started_at, completed_at, len(rows), affected, range_start, finished_range),
            )
            connection.commit()
        finally:
            cursor.close()
        return {
            "batch_id": batch_id,
            "status": "success",
            "rows_extracted": len(rows),
            "rows_affected": affected,
            "range_start": range_start.isoformat(),
            "range_end": finished_range.isoformat(),
        }
    except Exception as exc:
        connection.rollback()
        cursor = connection.cursor()
        try:
            cursor.execute(
                f"""
                insert into {audit_table}
                    (batch_id, started_at, completed_at, status, rows_extracted,
                     rows_affected, range_start, range_end, error_message)
                values (%s, %s, %s, 'failed', %s, 0, %s, %s, %s)
                """,
                (
                    batch_id,
                    started_at,
                    datetime.now(timezone.utc),
                    len(rows),
                    range_start,
                    finished_range,
                    str(exc)[:5000],
                ),
            )
            connection.commit()
        finally:
            cursor.close()
        raise
