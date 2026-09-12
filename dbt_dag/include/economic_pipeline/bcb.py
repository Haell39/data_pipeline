"""Small, testable client for Banco Central do Brasil SGS time series."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Iterable, Iterator, Mapping

import requests

BCB_SGS_URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{code}/dados"


@dataclass(frozen=True)
class SeriesDefinition:
    code: int
    key: str
    name: str
    category: str
    unit: str
    frequency: str
    aggregation: str
    display_order: int

    @property
    def source_url(self) -> str:
        return BCB_SGS_URL.format(code=self.code)


SERIES: tuple[SeriesDefinition, ...] = (
    SeriesDefinition(432, "selic_target", "Meta Selic", "Juros", "% a.a.", "daily", "last", 1),
    SeriesDefinition(433, "ipca_monthly", "IPCA mensal", "Inflação", "% a.m.", "monthly", "last", 2),
    SeriesDefinition(1, "usd_brl", "Dólar comercial", "Câmbio", "R$/US$", "daily", "last", 3),
    SeriesDefinition(24369, "unemployment", "Taxa de desocupação", "Trabalho", "%", "monthly", "last", 4),
)


def iter_date_chunks(start_date: date, end_date: date, days: int = 365) -> Iterator[tuple[date, date]]:
    """Yield inclusive ranges so daily SGS series never request an unbounded history."""
    if start_date > end_date:
        raise ValueError("start_date must be on or before end_date")
    if days < 1:
        raise ValueError("days must be positive")

    current = start_date
    while current <= end_date:
        chunk_end = min(current + timedelta(days=days - 1), end_date)
        yield current, chunk_end
        current = chunk_end + timedelta(days=1)


def parse_sgs_payload(
    definition: SeriesDefinition,
    payload: Iterable[Mapping[str, str]],
    loaded_at: datetime,
) -> list[dict[str, object]]:
    """Normalize the BCB JSON response and reject malformed observations."""
    rows: list[dict[str, object]] = []
    for item in payload:
        try:
            observation_date = datetime.strptime(item["data"], "%d/%m/%Y").date()
            value = Decimal(str(item["valor"]).replace(",", "."))
        except (KeyError, TypeError, ValueError, InvalidOperation) as exc:
            raise ValueError(f"Invalid SGS observation for series {definition.code}: {item}") from exc

        rows.append(
            {
                "series_code": definition.code,
                "indicator_key": definition.key,
                "indicator_name": definition.name,
                "category": definition.category,
                "unit": definition.unit,
                "frequency": definition.frequency,
                "aggregation": definition.aggregation,
                "display_order": definition.display_order,
                "observation_date": observation_date,
                "value": value,
                "source_url": definition.source_url,
                "loaded_at": loaded_at,
            }
        )
    return rows


def fetch_series(
    definition: SeriesDefinition,
    start_date: date,
    end_date: date,
    session: requests.Session | None = None,
    timeout: int = 30,
) -> list[dict[str, object]]:
    """Fetch one SGS series in bounded chunks and de-duplicate by date."""
    client = session or requests.Session()
    loaded_at = datetime.now(timezone.utc)
    observations: dict[date, dict[str, object]] = {}

    for chunk_start, chunk_end in iter_date_chunks(start_date, end_date):
        response = client.get(
            definition.source_url,
            params={
                "formato": "json",
                "dataInicial": chunk_start.strftime("%d/%m/%Y"),
                "dataFinal": chunk_end.strftime("%d/%m/%Y"),
            },
            timeout=timeout,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list):
            raise ValueError(f"Unexpected SGS response for series {definition.code}")
        for row in parse_sgs_payload(definition, payload, loaded_at):
            observations[row["observation_date"]] = row

    return [observations[key] for key in sorted(observations)]


def fetch_all_series(
    start_date: date,
    end_date: date,
    session: requests.Session | None = None,
) -> list[dict[str, object]]:
    """Fetch the intentionally small indicator catalog used by the project."""
    rows: list[dict[str, object]] = []
    client = session or requests.Session()
    for definition in SERIES:
        rows.extend(fetch_series(definition, start_date, end_date, session=client))
    return sorted(rows, key=lambda row: (row["series_code"], row["observation_date"]))


def build_monthly_snapshot(rows: Iterable[Mapping[str, object]]) -> list[dict[str, object]]:
    """Build a portable demo snapshot with the same grain as the dbt monthly mart."""
    grouped: dict[tuple[int, date], list[Mapping[str, object]]] = defaultdict(list)
    for row in rows:
        observation_date = row["observation_date"]
        if not isinstance(observation_date, date):
            raise TypeError("observation_date must be a date")
        month = observation_date.replace(day=1)
        grouped[(int(row["series_code"]), month)].append(row)

    monthly_rows: list[dict[str, object]] = []
    for (_, month), observations in grouped.items():
        ordered = sorted(observations, key=lambda row: row["observation_date"])
        latest = ordered[-1]
        values = [Decimal(str(row["value"])) for row in ordered]
        monthly_rows.append(
            {
                "month": month,
                "series_code": latest["series_code"],
                "indicator_key": latest["indicator_key"],
                "indicator_name": latest["indicator_name"],
                "category": latest["category"],
                "unit": latest["unit"],
                "frequency": latest["frequency"],
                "value": latest["value"],
                "monthly_average": (sum(values) / Decimal(len(values))).quantize(
                    Decimal("0.000001"), rounding=ROUND_HALF_UP
                ),
                "observation_count": len(values),
                "last_observation_date": latest["observation_date"],
                "loaded_at": latest["loaded_at"],
            }
        )
    return sorted(monthly_rows, key=lambda row: (row["month"], row["series_code"]))
