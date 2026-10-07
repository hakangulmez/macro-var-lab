"""Announced policy schedules: carry effective rate until the next announced change."""

import re

import pandas as pd
from bs4 import BeautifulSoup


def parse_schedule(payload: bytes, column: str) -> pd.Series:
    tables = BeautifulSoup(payload, "html.parser").find_all("table")
    candidates = [
        table
        for table in tables
        if "Lending" in table.get_text() and "Borrowing" in table.get_text()
    ]
    if len(candidates) != 1:
        raise ValueError("Expected one borrowing/lending policy table")
    dates, values = [], []
    offset = 1 if column == "Borrowing" else 2 if column == "Lending" else None
    if offset is None:
        raise ValueError("Unknown policy table column")
    for row in candidates[0].find_all("tr"):
        cells = [cell.get_text(" ", strip=True) for cell in row.find_all(["td", "th"])]
        if not cells or not re.fullmatch(r"\d{2}\.\d{2}\.\d{2,4}", cells[0]):
            continue
        if len(cells) != 3 or cells[offset] in ("", "-"):
            raise ValueError("Missing announced rate in dated table row")
        date = pd.to_datetime(cells[0], format="%d.%m.%y" if len(cells[0]) == 8 else "%d.%m.%Y")
        dates.append(date)
        values.append(float(cells[offset].replace(",", ".")))
    result = pd.Series(values, index=pd.DatetimeIndex(dates), dtype=float).sort_index()
    if result.empty or result.index.duplicated().any():
        raise ValueError("Missing/duplicate policy effective dates")
    return result


def announced_rate(overnight: pd.Series, repo: pd.Series, start: str, end: str) -> pd.Series:
    cut = pd.Timestamp("2010-05-20")
    if cut not in repo.index or not (overnight.index < pd.Timestamp(start)).any():
        raise ValueError("Insufficient effective-date boundary coverage")
    steps = pd.concat([overnight.loc[overnight.index < cut], repo.loc[repo.index >= cut]])
    daily = pd.date_range(start, end, freq="D")
    # Reindex the complete announced event schedule, including pre-sample anchor.
    # Holding a known scheduled rate is not filling missing macro observations.
    known = steps.reindex(steps.index.union(daily)).sort_index().ffill().reindex(daily)
    if known.isna().any():
        raise ValueError("Unknown scheduled rate")
    return known.groupby(known.index.to_period("M")).mean()
