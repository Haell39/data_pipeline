"""Core utilities for the Brazilian economic indicators pipeline."""

from .bcb import SERIES, build_monthly_snapshot, fetch_all_series

__all__ = ["SERIES", "build_monthly_snapshot", "fetch_all_series"]
