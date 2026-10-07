"""Credential-safe, bounded public-data requests and immutable response caching."""

import hashlib
import json
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode, urlsplit
from zoneinfo import ZoneInfo

import requests


class AccessError(RuntimeError):
    """Safe error carrying no URL, key or response body."""


def read_keys(path: Path) -> dict[str, str]:
    keys: dict[str, str] = {}
    if not path.exists():
        return keys
    for line in path.read_text().splitlines():
        key, sep, value = line.strip().removeprefix("export ").partition("=")
        if sep and key.strip() in ("EVDS_API_KEY", "FRED_API_KEY"):
            value = value.strip().strip("\"'")
            if value:
                keys[key.strip()] = value
    return keys


class Client:
    def __init__(self, root: Path, limit: int = 30_000_000):
        if "CloudStorage" in root.resolve().parts:
            raise ValueError("Run on local disk only")
        self.directory = root / "data/raw/responses"
        self.directory.mkdir(parents=True, exist_ok=True)
        self.limit = limit
        self.last_start = 0.0
        self.records: dict[str, dict] = {}

    def get(
        self,
        label: str,
        url: str,
        params: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
    ) -> bytes:
        """Retry public ECB transient failures five times at most (1,2,4,8s)."""
        public_ecb = urlsplit(url).hostname == "data-api.ecb.europa.eu" and not headers
        public_ecb = public_ecb and "api_key" not in (params or {})
        if not public_ecb:
            return self._get_once(label, url, params, headers)
        endpoint = url + ("?" + urlencode(params) if params else "")
        for attempt in range(1, 6):
            try:
                return self._get_once(label, url, params, headers)
            except AccessError as error:
                reason = str(error)
                transient = "Network request failed" in reason or any(
                    f"HTTP {code}" in reason for code in [429, *range(500, 600)]
                )
                if not transient or attempt == 5:
                    raise AccessError(
                        f"ECB acquisition failed after {attempt} attempt(s): "
                        f"endpoint={endpoint}; {reason}"
                    ) from None
                time.sleep(2 ** (attempt - 1))
        raise AssertionError("Unreachable retry state")

    def _get_once(
        self,
        label: str,
        url: str,
        params: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
    ) -> bytes:
        params = params or {}
        safe_params = {k: v for k, v in params.items() if k != "api_key"}
        safe_url = url + ("?" + urlencode(safe_params) if safe_params else "")
        token = hashlib.sha256(safe_url.encode()).hexdigest()
        meta = self.directory / f"{token}.json"
        target = self.directory / f"{token}.bin"
        if meta.exists():
            record = json.loads(meta.read_text())
            if target.exists():
                content = target.read_bytes()
                if hashlib.sha256(content).hexdigest() != record["sha256"]:
                    raise AccessError("Cached response checksum mismatch")
                self.records[label] = record | {"cached": True}
                return content
            if (
                record["http_status"] < 500
                and record["http_status"] != 429
                and record["access_date"]
                == datetime.now(ZoneInfo("Europe/Berlin")).date().isoformat()
            ):
                raise AccessError(f"Cached daily failure: HTTP {record['http_status']}")
        time.sleep(max(0.0, 1.05 - (time.monotonic() - self.last_start)))
        self.last_start = time.monotonic()
        try:
            with requests.get(
                url,
                params=params,
                headers=headers,
                timeout=60,
                stream=True,
                allow_redirects=not bool(headers or "api_key" in params),
            ) as response:
                record = {
                    "url": safe_url,
                    "access_date": datetime.now(ZoneInfo("Europe/Berlin")).date().isoformat(),
                    "http_status": response.status_code,
                    "content_type": response.headers.get("Content-Type"),
                    "cached": False,
                }
                if response.status_code != 200:
                    meta.write_text(json.dumps(record, indent=2) + "\n")
                    self.records[label] = record
                    raise AccessError(f"HTTP {response.status_code}")
                buffer = bytearray()
                for chunk in response.iter_content(65536):
                    buffer.extend(chunk)
                    if len(buffer) > self.limit:
                        raise AccessError("Response exceeds configured byte cap")
        except requests.RequestException as error:
            raise AccessError(
                f"Network request failed ({type(error).__name__}); sensitive details suppressed"
            ) from None
        payload = bytes(buffer)
        sensitive = [value for key, value in params.items() if key == "api_key"]
        sensitive += [value for key, value in (headers or {}).items() if key.casefold() == "key"]
        if any(value.encode() in payload for value in sensitive if value):
            raise AccessError("Provider response contains a credential; not persisted")
        record.update(bytes=len(payload), sha256=hashlib.sha256(payload).hexdigest())
        temporary = target.with_suffix(".tmp")
        temporary.write_bytes(payload)
        temporary.replace(target)
        meta.write_text(json.dumps(record, indent=2) + "\n")
        self.records[label] = record
        return payload
