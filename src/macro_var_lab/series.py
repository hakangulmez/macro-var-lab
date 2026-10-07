"""Strict official-format parsers; no interpolation or arbitrary selector changes."""

import io
import json
import re
from typing import Any

import numpy as np
import pandas as pd


def clean(values: pd.Series) -> pd.Series:
    if values.index.duplicated().any():
        raise ValueError("Duplicate observation dates")
    return pd.to_numeric(values, errors="coerce").sort_index().astype(float)


def eurostat(payload: bytes, selectors: dict[str, str]) -> pd.Series:
    dataset = json.loads(payload)
    for dimension in dataset["id"]:
        if dimension != "time":
            indices = dataset["dimension"][dimension]["category"]["index"]
            if set(indices) != {selectors[dimension]}:
                raise ValueError("Eurostat selector mismatch")
    if dataset["id"][-1] != "time":
        raise ValueError("Unsupported time dimension layout")
    dates = dataset["dimension"]["time"]["category"]["index"]
    data = dataset["value"]
    values = [
        data.get(str(index)) if isinstance(data, dict) else data[index] for index in dates.values()
    ]
    return clean(pd.Series(values, index=pd.PeriodIndex(dates.keys(), freq="M")))


def ecb(payload: bytes, expected_key: str) -> pd.Series:
    table = pd.read_csv(io.BytesIO(payload), dtype=str)
    if set(table["KEY"].dropna()) != {expected_key}:
        raise ValueError("ECB key mismatch")
    index = (
        pd.PeriodIndex(table["TIME_PERIOD"], freq="M")
        if expected_key.split(".")[1] == "M"
        else pd.DatetimeIndex(table["TIME_PERIOD"])
    )
    return clean(pd.Series(table["OBS_VALUE"].to_numpy(), index=index))


def bundesbank(payload: bytes, expected_id: str) -> pd.Series:
    table = pd.read_csv(io.BytesIO(payload), dtype=str, encoding="utf-8-sig")
    if table.columns[1] != expected_id:
        raise ValueError("Bundesbank identifier mismatch")
    selected = table[table.iloc[:, 0].str.fullmatch(r"\d{4}-\d{2}-\d{2}", na=False)]
    return clean(
        pd.Series(selected.iloc[:, 1].to_numpy(), index=pd.DatetimeIndex(selected.iloc[:, 0]))
    )


def fred(payload: bytes, series_id: str, route: str) -> pd.Series:
    dates: Any
    values: Any
    if route == "public_csv":
        table = pd.read_csv(io.BytesIO(payload), dtype=str)
        if list(table.columns) != ["observation_date", series_id]:
            raise ValueError("FRED CSV schema mismatch")
        dates, values = table.iloc[:, 0], table.iloc[:, 1]
    else:
        data = json.loads(payload)
        if data.get("count") != len(data["observations"]):
            raise ValueError("FRED pagination required; refusing truncated response")
        dates = [row["date"] for row in data["observations"]]
        values = [row["value"] for row in data["observations"]]
    return clean(pd.Series(np.asarray(values), index=pd.DatetimeIndex(dates)))


def evds(payload: bytes, series_id: str) -> pd.Series:
    data = json.loads(payload)
    rows = data["items"]
    if int(data.get("totalCount", len(rows))) != len(rows):
        raise ValueError("EVDS pagination/truncation mismatch")
    column = series_id.replace(".", "_")
    dates, values = [], []
    monthly = True
    for row in rows:
        date = str(row["Tarih"])
        if re.fullmatch(r"\d{4}-\d{1,2}", date):
            dates.append(pd.Period(date, freq="M").to_timestamp())
        else:
            monthly = False
            dates.append(
                pd.Timestamp(date)
                if re.fullmatch(r"\d{4}-\d{2}-\d{2}", date)
                else pd.to_datetime(date, format="%d-%m-%Y")
            )
        if column not in row:
            raise ValueError("EVDS series column missing")
        values.append(row[column])
    index: Any = pd.DatetimeIndex(dates)
    if monthly:
        index = index.to_period("M")
    return clean(pd.Series(values, index=index))


def monthly(series: pd.Series, end: str) -> tuple[pd.Series, dict[str, int]]:
    if isinstance(series.index, pd.PeriodIndex):
        if series.index.freqstr != "M":
            raise ValueError("Expected monthly period index")
        return series.loc[: pd.Period(end, freq="M")], {}
    daily = series.loc[: pd.Timestamp(end)]
    groups = daily.groupby(pd.DatetimeIndex(daily.index).to_period("M"))
    return groups.mean(), {str(k): int(v) for k, v in groups.count().items()}


def transform(series: pd.Series, kind: str, differenced: bool = False) -> pd.Series:
    if kind in ("log100", "log"):
        if (series.dropna() <= 0).any():
            raise ValueError("Nonpositive observation in logged series")
        result = np.log(series) * (100 if kind == "log100" else 1)
    elif kind == "rate":
        result = series.copy()
    else:
        raise ValueError("Unknown transformation")
    # Reindex monthly before differencing: never bridge across a missing month.
    if len(result):
        result = result.reindex(pd.period_range(result.index.min(), result.index.max(), freq="M"))
    return result.diff() if differenced else result


def price_bridge(old: pd.Series, new: pd.Series, tolerance: float = 0.002) -> dict:
    overlap = pd.concat([old.rename("old"), new.rename("new")], axis=1).dropna()
    if len(overlap) < 12 or (overlap <= 0).any().any():
        return {"status": "insufficient_overlap", "overlap_months": len(overlap)}
    ratio = overlap["new"] / overlap["old"]
    spread = float(ratio.max() / ratio.min() - 1)
    return {
        "status": "ratio_stable" if spread <= tolerance else "incompatible_rebase",
        "overlap_months": len(overlap),
        "ratio_relative_range": spread,
        "median_ratio": float(ratio.median()),
        "tolerance": tolerance,
        "classification_review_required": True,
        "automatically_spliced": False,
    }
