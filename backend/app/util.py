"""Small shared helpers for the API layer."""

from datetime import date

from fastapi import HTTPException


def parse_month(value: str) -> date:
    """Parse a 'YYYY-MM' string into the first day of that month."""
    try:
        year, month = value.split("-")
        d = date(int(year), int(month), 1)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=422, detail=f"invalid month {value!r}, expected YYYY-MM")
    return d


def next_month(d: date) -> date:
    """First day of the month after `d` (d is assumed to be a first-of-month)."""
    return date(d.year + 1, 1, 1) if d.month == 12 else date(d.year, d.month + 1, 1)


def pct(part: int, whole: int) -> float | None:
    """part/whole as a rounded percentage, or None when whole == 0."""
    return round(part / whole * 100, 1) if whole else None
