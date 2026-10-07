"""Bound retries and preserve the public endpoint while hiding other credentials."""

import pytest

from macro_var_lab.access import AccessError, Client

URL = "https://data-api.ecb.europa.eu/service/data/YC/test"


def test_ecb_recovers_transient_failure(tmp_path, monkeypatch):
    client = Client(tmp_path)
    starts, delays = [], []

    def get(*args):
        starts.append(args)
        if len(starts) < 3:
            raise AccessError("HTTP 504")
        return b"ok"

    monkeypatch.setattr(client, "_get_once", get)
    monkeypatch.setattr("macro_var_lab.access.time.sleep", delays.append)
    assert client.get("yield", URL) == b"ok"
    assert len(starts) == 3 and delays == [1, 2]


def test_ecb_stops_at_five_and_reports_endpoint(tmp_path, monkeypatch):
    client = Client(tmp_path)
    calls, delays = [], []

    def get(*args):
        calls.append(args)
        raise AccessError("HTTP 503")

    monkeypatch.setattr(client, "_get_once", get)
    monkeypatch.setattr("macro_var_lab.access.time.sleep", delays.append)
    with pytest.raises(AccessError, match="after 5 attempt") as exc:
        client.get("yield", URL, {"startPeriod": "2004-09"})
    assert URL + "?startPeriod=2004-09" in str(exc.value)
    assert "HTTP 503" in str(exc.value)
    assert len(calls) == 5 and delays == [1, 2, 4, 8]


def test_ecb_permanent_error_and_other_provider_are_not_retried(tmp_path, monkeypatch):
    client = Client(tmp_path)
    calls = []

    def get(*args):
        calls.append(args)
        raise AccessError("HTTP 404")

    monkeypatch.setattr(client, "_get_once", get)
    with pytest.raises(AccessError, match="after 1 attempt"):
        client.get("yield", URL)
    with pytest.raises(AccessError, match="^HTTP 404$"):
        client.get(
            "fred", "https://api.stlouisfed.org/fred/series/observations", {"api_key": "not-real"}
        )
    assert len(calls) == 2


def test_rate_limit_failure_is_not_reused_as_a_daily_cached_failure(tmp_path, monkeypatch):
    """A 429 must issue a new HTTP request after backoff, rather than reread its cache."""
    client = Client(tmp_path)
    statuses = iter([429, 200])
    calls = []

    class Response:
        headers = {"Content-Type": "text/csv"}

        def __init__(self, status):
            self.status_code = status

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def iter_content(self, size):
            yield b"DATE,OBS_VALUE\n2026-07,2\n"

    def get(*args, **kwargs):
        calls.append(args)
        return Response(next(statuses))

    monkeypatch.setattr("macro_var_lab.access.requests.get", get)
    monkeypatch.setattr("macro_var_lab.access.time.sleep", lambda _: None)
    assert b"2026-07" in client.get("yield", URL)
    assert len(calls) == 2 and client.records["yield"]["http_status"] == 200
