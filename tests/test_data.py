import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import requests

from macro_var_lab import checks, series
from macro_var_lab.access import AccessError, Client, read_keys
from macro_var_lab.data import Config, Spec, acquire
from macro_var_lab.policy import announced_rate, parse_schedule


def test_levels_baseline_and_differences_do_not_bridge_missing_months():
    index = pd.PeriodIndex(["2000-01", "2000-03", "2000-04"], freq="M")
    raw = pd.Series([100.0, 110.0, 121.0], index=index)
    levels = series.transform(raw, "log100")
    diff = series.transform(raw, "log100", True)
    assert levels.loc["2000-01"] == pytest.approx(100 * np.log(100))
    assert pd.isna(diff.loc["2000-03"])
    assert diff.loc["2000-04"] == pytest.approx(100 * np.log(1.1))
    rates = pd.Series([-0.5, 1.0, 3.0], index=pd.period_range("2000-01", periods=3, freq="M"))
    pd.testing.assert_series_equal(series.transform(rates, "rate"), rates)
    with pytest.raises(ValueError, match="Nonpositive"):
        series.transform(rates, "log")
    with pytest.raises(ValueError, match="Unknown"):
        series.transform(raw, "invalid")


def test_jsonstat_sparse_observations_and_selector_integrity():
    payload = {
        "id": ["geo", "time"],
        "dimension": {
            "geo": {"category": {"index": {"EA21": 0}}},
            "time": {"category": {"index": {"2000-01": 0, "2000-02": 1, "2000-03": 2}}},
        },
        "value": {"0": 1, "2": 3},
    }
    result = series.eurostat(json.dumps(payload).encode(), {"geo": "EA21"})
    assert result.loc["2000-01"] == 1 and pd.isna(result.loc["2000-02"])
    with pytest.raises(ValueError, match="selector"):
        series.eurostat(json.dumps(payload).encode(), {"geo": "EA20"})
    payload["value"] = [1, None, 3]
    assert series.eurostat(json.dumps(payload).encode(), {"geo": "EA21"}).loc["2000-03"] == 3
    payload["id"] = ["time", "geo"]
    with pytest.raises(ValueError, match="time dimension"):
        series.eurostat(json.dumps(payload).encode(), {"geo": "EA21"})


def test_csv_series_identity_missing_values_duplicates_and_monthly_mean():
    data = b"KEY,TIME_PERIOD,OBS_VALUE\nYC.B.TEST,2004-09-06,-0.5\nYC.B.TEST,2004-09-07,0.5\n"
    result, counts = series.monthly(series.ecb(data, "YC.B.TEST"), "2004-09-30")
    assert result.iloc[0] == 0 and counts == {"2004-09": 2}
    with pytest.raises(ValueError, match="key"):
        series.ecb(data, "YC.B.OTHER")
    with pytest.raises(ValueError, match="Duplicate"):
        series.ecb(data + b"YC.B.TEST,2004-09-06,1\n", "YC.B.TEST")
    bb = b",BBSIS.D.TEST,FLAGS\nunit,Percent,\n1999-01-01,.,missing\n1999-01-04,3.5,\n"
    assert series.bundesbank(bb, "BBSIS.D.TEST").dropna().iloc[0] == 3.5
    with pytest.raises(ValueError, match="identifier"):
        series.bundesbank(bb, "BBSIS.D.OTHER")
    monthly_data = b"KEY,TIME_PERIOD,OBS_VALUE\nFM.M.TEST,1999-01,3.5\n"
    out, counts = series.monthly(series.ecb(monthly_data, "FM.M.TEST"), "1999-01-31")
    assert out.iloc[0] == 3.5 and counts == {}
    with pytest.raises(ValueError, match="monthly"):
        series.monthly(
            pd.Series([1], index=pd.period_range("2000", periods=1, freq="Y")), "2001-01-01"
        )


def test_fred_and_evds_native_format_pagination_and_date_parsing():
    csv = b"observation_date,DEXUSEU\n1999-01-04,1.1\n1999-01-05,.\n"
    assert series.fred(csv, "DEXUSEU", "public_csv").notna().sum() == 1
    with pytest.raises(ValueError, match="schema"):
        series.fred(csv, "OTHER", "public_csv")
    observations = {"count": 1, "observations": [{"date": "2000-01-01", "value": "5"}]}
    assert series.fred(json.dumps(observations).encode(), "FEDFUNDS", "api").iloc[0] == 5
    observations["count"] = 10
    with pytest.raises(ValueError, match="pagination"):
        series.fred(json.dumps(observations).encode(), "FEDFUNDS", "api")
    evds = {
        "totalCount": 2,
        "items": [{"Tarih": "2006-1", "TP_TEST": "100"}, {"Tarih": "2006-2", "TP_TEST": None}],
    }
    assert isinstance(series.evds(json.dumps(evds).encode(), "TP.TEST").index, pd.PeriodIndex)
    evds["items"][0]["Tarih"] = "2006-01-02"
    evds["items"][1]["Tarih"] = "03-01-2006"
    parsed = series.evds(json.dumps(evds).encode(), "TP.TEST")
    assert parsed.index[0] == pd.Timestamp("2006-01-02")
    evds["totalCount"] = 3
    with pytest.raises(ValueError, match="truncation"):
        series.evds(json.dumps(evds).encode(), "TP.TEST")
    evds["totalCount"] = 2
    with pytest.raises(ValueError, match="column"):
        series.evds(json.dumps(evds).encode(), "TP.OTHER")


def test_price_bridge_requires_overlap_and_never_automatically_splices():
    index = pd.period_range("2000-01", periods=24, freq="M")
    old = pd.Series(np.arange(100.0, 124.0), index=index)
    assert series.price_bridge(old.iloc[:1], old.iloc[:1])["status"] == "insufficient_overlap"
    stable = series.price_bridge(old, old * 2)
    assert stable["status"] == "ratio_stable" and not stable["automatically_spliced"]
    changed = old * 2
    changed.iloc[10:] *= 1.1
    assert series.price_bridge(old, changed)["status"] == "incompatible_rebase"


def test_known_policy_steps_not_missing_macro_interpolation():
    table = (
        b"<table><tr><th>Date</th><th>Borrowing</th><th>Lending</th></tr>"
        b"<tr><td>02.01.06</td><td>13.50</td><td>16.50</td></tr>"
        b"<tr><td>20.05.2010</td><td>6.50</td><td>7,00</td></tr></table>"
    )
    on = parse_schedule(table, "Borrowing")
    repo = parse_schedule(table, "Lending")
    monthly = announced_rate(on, repo, "2006-02-01", "2010-05-31")
    assert monthly.loc["2010-05"] == pytest.approx((19 * 13.5 + 12 * 7) / 31)
    with pytest.raises(ValueError, match="Unknown"):
        parse_schedule(table, "invalid")
    with pytest.raises(ValueError, match="Expected"):
        parse_schedule(b"<table><td>Other table</td></table>", "Lending")
    with pytest.raises(ValueError, match="boundary"):
        announced_rate(on, repo.iloc[:1], "2006-02-01", "2010-05-31")


def test_checks_expose_missing_dates_and_do_not_change_transforms():
    data = pd.Series(
        [1.0, 2.0, np.nan, 4.0, 5.0], index=pd.period_range("2000-01", periods=5, freq="M")
    )
    assert checks.longest_complete(data).index[0] == pd.Period("2000-01")
    result = checks.coverage(data, "2000-01", "2000-05")
    assert result["missing_dates"] == ["2000-03"] and not result["interpolated"]
    sample = checks.panel_sample(pd.DataFrame({"a": data}), ["a"], "2000-01", "2000-05")
    assert sample["status"] == "coverage_gap" and sample["complete_months"] == 4
    assert (
        checks.panel_sample(pd.DataFrame({"a": data}), ["b"], "2000-01", "2000-05")["status"]
        == "blocked"
    )
    assert checks.diagnostics(data)["status"] == "insufficient_sample"
    rng = np.random.default_rng(20261007)
    values = pd.Series(
        rng.normal(size=120), index=pd.period_range("2000-01", periods=120, freq="M")
    )
    before = values.copy()
    results = checks.diagnostics(values)
    assert results["ADF_c"]["pvalue"] < 0.05
    assert all(key in results for key in ("KPSS_ct", "PP_c", "ZA_ct"))
    assert not results["baseline_transform_changed"]
    pd.testing.assert_series_equal(before, values)


class Response:
    def __init__(self, payload=b'{"value":1}', status=200):
        self.payload, self.status_code = payload, status
        self.headers = {"Content-Type": "application/json"}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def iter_content(self, size):
        yield self.payload


def test_http_credentials_never_in_manifest_errors_or_cache(tmp_path: Path, monkeypatch):
    path = tmp_path / ".env"
    path.write_text("export EVDS_API_KEY='fixture-not-real'\nFRED_API_KEY=fixture-fred\nOTHER=no\n")
    assert set(read_keys(path)) == {"EVDS_API_KEY", "FRED_API_KEY"}
    assert read_keys(tmp_path / "absent") == {}
    calls = []

    def get(*args, **kwargs):
        calls.append(kwargs)
        return Response()

    monkeypatch.setattr(requests, "get", get)
    client = Client(tmp_path)
    assert client.get("test", "https://example.test", {"api_key": "fixture-fred"})
    assert not calls[0]["allow_redirects"]
    assert "fixture-fred" not in json.dumps(client.records)
    assert client.get("test", "https://example.test", {"api_key": "fixture-fred"})
    assert len(calls) == 1 and client.records["test"]["cached"]
    monkeypatch.setattr(requests, "get", lambda *a, **kw: Response(b"fixture-fred"))
    with pytest.raises(AccessError, match="credential"):
        client.get("echo", "https://echo.test", {"api_key": "fixture-fred"})
    monkeypatch.setattr(requests, "get", lambda *a, **kw: Response(status=403))
    with pytest.raises(AccessError, match="HTTP 403"):
        client.get("failure", "https://failure.test")
    with pytest.raises(AccessError, match="Cached daily failure"):
        client.get("failure", "https://failure.test")


def test_source_key_requirements_are_explicit_not_silent_substitutions(tmp_path: Path):
    client = Client(tmp_path)
    config = Config(
        seed=20261007, start="2006-01-01", end="2026-09-30", fred_route="api", series=[]
    )
    spec = Spec(
        name="tr_ip",
        provider="evds",
        identifier="TP.TEST",
        transform="log100",
        adjustment="SCA",
        role="TR",
    )
    with pytest.raises(AccessError, match="EVDS_API_KEY"):
        acquire(client, spec, config, {})
    spec.provider = "fred"
    with pytest.raises(AccessError, match="FRED_API_KEY"):
        acquire(client, spec, config, {})


def test_offline_pipeline_covers_levels_without_overwriting_research(tmp_path: Path, monkeypatch):
    import subprocess

    from macro_var_lab.quick import quick

    root = Path(__file__).parents[1]
    (tmp_path / "configs").mkdir()
    (tmp_path / "configs/data.yaml").write_bytes((root / "configs/data.yaml").read_bytes())
    (tmp_path / "configs/g2.yaml").write_bytes((root / "configs/g2.yaml").read_bytes())
    (tmp_path / "results").mkdir()
    marker = tmp_path / "results/g1_data_checks.json"
    marker.write_text('{"preserve":true}')
    provenance = tmp_path / "results/source_checksums.json"
    provenance.write_text('{"source_evidence":"preserve"}')
    monkeypatch.setattr(
        subprocess, "check_output", lambda *a, **kw: "fixture-commit\n" if kw.get("text") else b""
    )
    monkeypatch.setattr(requests, "get", lambda *a, **kw: pytest.fail("Quick must be offline"))
    result = quick(tmp_path)
    assert result["series_checked"] == 21 and result["network_calls"] == 0
    assert marker.read_text() == '{"preserve":true}'
    assert provenance.read_text() == '{"source_evidence":"preserve"}'


def test_evds_date_windows_respect_hidden_backward_limit(tmp_path, monkeypatch):
    from macro_var_lab.data import evds_windows

    windows = evds_windows("1998-12-01", "2026-09-30", "business_daily")
    assert windows[0][0] == "1998-12-01" and windows[-1][1] == "2026-09-30"
    for (start, end), following in zip(windows, windows[1:] + [None], strict=True):
        assert (pd.Timestamp(end) - pd.Timestamp(start)).days < 1000
        if following:
            assert pd.Timestamp(end) + pd.Timedelta(days=1) == pd.Timestamp(following[0])
    assert evds_windows("2006-01-01", "2026-09-30", "monthly") == [("2006-01-01", "2026-09-30")]
    with pytest.raises(ValueError, match="native frequency"):
        evds_windows("2006-01-01", "2026-09-30", None)
    spec = Spec(
        name="usdtry",
        provider="evds",
        identifier="TP.TEST",
        transform="log100",
        adjustment="NSA",
        role="TR",
        native_frequency="daily",
    )
    config = Config(seed=1, start="2000-01-01", end="2003-12-31", fred_route="api", series=[spec])

    class Fake:
        def get(self, label, url, **kwargs):
            date = "01-01-2000" if "startDate=01-01-2000" in url else "01-01-2002"
            return json.dumps(
                {"totalCount": 1, "items": [{"Tarih": date, "TP_TEST": "2"}]}
            ).encode()

    assert len(acquire(Fake(), spec, config, {"EVDS_API_KEY": "dummy"})) == 2

    class Saturated:
        def get(self, *args, **kwargs):
            return json.dumps({"totalCount": 1000, "items": [{}] * 1000}).encode()

    with pytest.raises(ValueError, match="saturation"):
        acquire(Saturated(), spec, config, {"EVDS_API_KEY": "dummy"})


def test_fred_api_is_explicit_and_never_silently_falls_back(tmp_path):
    calls = []

    class Fake:
        def get(self, label, url, params):
            calls.append((url, params))
            return json.dumps(
                {"count": 1, "observations": [{"date": "2000-01-01", "value": "5"}]}
            ).encode()

    config = Config(seed=1, start="2000-01-01", end="2000-01-31", fred_route="api", series=[])
    spec = Spec(
        name="rate",
        provider="fred",
        identifier="FEDFUNDS",
        transform="rate",
        adjustment="NSA",
        role="external",
    )
    assert acquire(Fake(), spec, config, {"FRED_API_KEY": "dummy"}).iloc[0] == 5
    assert calls[0][0] == "https://api.stlouisfed.org/fred/series/observations"
    assert calls[0][1]["limit"] == "100000" and "frequency" not in calls[0][1]
    assert len(calls) == 1


def test_supplementary_checks_preserve_growth_gaps_and_reveal_rate_difference():
    index = pd.period_range("2006-01", periods=4, freq="M")
    data = pd.DataFrame(
        {
            "tr_cpi_old": [100, 110, np.nan, 1000],
            "tr_cpi": [50, 55, np.nan, 500],
            "tr_aofm": [np.nan, 5, 7, 9],
            "tr_announced": [4, 4, 6, 8],
        },
        index=index,
    )
    bridges, policy = checks.supplementary(data, "2006-04")
    assert bridges["headline"]["max_abs_monthly_log_growth_gap_pp"] == pytest.approx(0)
    assert not bridges["headline"]["no_splice_needed_for_target"]
    assert policy["overlap_months"] == 3 and policy["mean_abs_gap_pp"] == 1
    assert policy["overlap_start"] == "2006-02" and not policy["AOFM_substituted"]
    assert (
        checks.supplementary(data.drop(columns="tr_aofm"), "2006-04")[1]["status"] == "unavailable"
    )
    data["tr_aofm"] = np.nan
    assert checks.supplementary(data, "2006-04")[1]["status"] == "unavailable"
