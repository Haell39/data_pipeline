"""Refresh the credential-free dataset used by the public Streamlit demo."""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
AIRFLOW_INCLUDE = PROJECT_ROOT / "dbt_dag" / "include"
sys.path.insert(0, str(AIRFLOW_INCLUDE))

from economic_pipeline import build_monthly_snapshot, fetch_all_series  # noqa: E402

DEFAULT_OUTPUT = PROJECT_ROOT / "app" / "data" / "economic_monthly.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-date", type=date.fromisoformat, default=date(2020, 1, 1))
    parser.add_argument("--end-date", type=date.fromisoformat, default=date.today())
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def serialize(value: object) -> str:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def main() -> None:
    args = parse_args()
    raw_rows = fetch_all_series(args.start_date, args.end_date)
    monthly_rows = build_monthly_snapshot(raw_rows)
    if not monthly_rows:
        raise RuntimeError("BCB returned no observations")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(monthly_rows[0])
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows({key: serialize(value) for key, value in row.items()} for row in monthly_rows)

    print(f"Wrote {len(monthly_rows)} monthly observations to {args.output}")


if __name__ == "__main__":
    main()
