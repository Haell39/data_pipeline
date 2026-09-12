from datetime import date, datetime, timezone
from decimal import Decimal
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "dbt_dag" / "include"))

from economic_pipeline.bcb import SERIES, build_monthly_snapshot, iter_date_chunks, parse_sgs_payload


def test_iter_date_chunks_is_inclusive_without_gaps():
    chunks = list(iter_date_chunks(date(2024, 1, 1), date(2024, 1, 5), days=2))
    assert chunks == [
        (date(2024, 1, 1), date(2024, 1, 2)),
        (date(2024, 1, 3), date(2024, 1, 4)),
        (date(2024, 1, 5), date(2024, 1, 5)),
    ]


def test_parse_sgs_payload_normalizes_decimal_and_date():
    loaded_at = datetime(2026, 9, 12, tzinfo=timezone.utc)
    row = parse_sgs_payload(SERIES[1], [{"data": "01/08/2026", "valor": "-0,10"}], loaded_at)[0]
    assert row["observation_date"] == date(2026, 8, 1)
    assert row["value"] == Decimal("-0.10")
    assert row["indicator_key"] == "ipca_monthly"


def test_build_monthly_snapshot_uses_last_value_and_monthly_average():
    loaded_at = datetime(2026, 9, 12, tzinfo=timezone.utc)
    base = {
        "series_code": 432,
        "indicator_key": "selic_target",
        "indicator_name": "Meta Selic",
        "category": "Juros",
        "unit": "% a.a.",
        "frequency": "daily",
        "loaded_at": loaded_at,
    }
    rows = [
        {**base, "observation_date": date(2026, 1, 2), "value": Decimal("15.00")},
        {**base, "observation_date": date(2026, 1, 30), "value": Decimal("14.75")},
    ]
    monthly = build_monthly_snapshot(rows)[0]
    assert monthly["value"] == Decimal("14.75")
    assert monthly["monthly_average"] == Decimal("14.875000")
    assert monthly["observation_count"] == 2
