"""G1 source acquisition, monthly checks and auditable sample readiness."""

import hashlib
import json
import platform
import shutil
import subprocess
import time
from datetime import datetime
from importlib.metadata import distributions
from pathlib import Path
from typing import Any, Literal
from zoneinfo import ZoneInfo

import pandas as pd
import yaml
from pydantic import BaseModel, ConfigDict

from macro_var_lab import series
from macro_var_lab.access import AccessError, Client, read_keys
from macro_var_lab.checks import coverage, diagnostics, panel_sample, supplementary
from macro_var_lab.policy import announced_rate, parse_schedule


class Spec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    provider: Literal["eurostat", "ecb", "bundesbank", "fred", "evds"]
    identifier: str
    transform: Literal["log100", "log", "rate"]
    adjustment: str
    role: str
    selectors: dict[str, str] = {}
    native_frequency: Literal["monthly", "business_daily", "daily"] | None = None


class Config(BaseModel):
    model_config = ConfigDict(extra="forbid")
    seed: int
    start: str
    end: str
    fred_route: Literal["public_csv", "api"]
    ea_baseline_start: str = "2004-09"
    ea_baseline_end: str = "2026-07"
    ea_robustness_start: str = "1999-12"
    series: list[Spec]


def acquire(client: Client, spec: Spec, config: Config, keys: dict[str, str]) -> pd.Series:
    start, end = config.start, config.end
    if spec.provider == "eurostat":
        content = client.get(
            spec.name,
            "https://ec.europa.eu/eurostat/api/dissemination/"
            f"statistics/1.0/data/{spec.identifier}",
            {"lang": "en", **spec.selectors},
        )
        return series.eurostat(content, spec.selectors)
    if spec.provider == "ecb":
        dataset, key = spec.identifier.split(".", 1)
        content = client.get(
            spec.name,
            f"https://data-api.ecb.europa.eu/service/data/{dataset}/{key}",
            {"startPeriod": start, "endPeriod": end, "format": "csvdata"},
        )
        return series.ecb(content, spec.identifier)
    if spec.provider == "bundesbank":
        dataset, key = spec.identifier.split(".", 1)
        content = client.get(
            spec.name,
            f"https://api.statistiken.bundesbank.de/rest/data/{dataset}/{key}",
            {"format": "csv", "lang": "en"},
        )
        return series.bundesbank(content, spec.identifier)
    if spec.provider == "fred":
        if config.fred_route == "api":
            if "FRED_API_KEY" not in keys:
                raise AccessError("Missing FRED_API_KEY in local .env")
            content = client.get(
                spec.name,
                "https://api.stlouisfed.org/fred/series/observations",
                {
                    "series_id": spec.identifier,
                    "api_key": keys["FRED_API_KEY"],
                    "file_type": "json",
                    "observation_start": start,
                    "observation_end": end,
                    "limit": "100000",
                },
            )
        else:
            content = client.get(
                spec.name,
                "https://fred.stlouisfed.org/graph/fredgraph.csv",
                {"id": spec.identifier, "cosd": start, "coed": end},
            )
        return series.fred(content, spec.identifier, config.fred_route)
    if "EVDS_API_KEY" not in keys:
        raise AccessError("Missing EVDS_API_KEY in local .env")
    url = "https://evds3.tcmb.gov.tr/igmevdsms-dis/"
    # Native frequency and formula defaults; aggregate daily series locally, never ask
    # the service to interpolate. Authenticated route must not follow redirects.
    windows = evds_windows(start, end, spec.native_frequency)
    parts = []
    for first, last in windows:
        label = spec.name if len(windows) == 1 else f"{spec.name}:{first}:{last}"
        content = client.get(
            label,
            url
            + f"series={spec.identifier}&startDate="
            + pd.Timestamp(first).strftime("%d-%m-%Y")
            + "&endDate="
            + pd.Timestamp(last).strftime("%d-%m-%Y")
            + "&type=json",
            headers={"key": keys["EVDS_API_KEY"]},
        )
        # EVDS 3 returns only the last 1,000 rows and reports that as totalCount.
        # Saturation is therefore an error even when count == len(items).
        if len(json.loads(content)["items"]) >= 1000:
            raise ValueError("EVDS 1000-row saturation; shorten request window")
        part = series.evds(content, spec.identifier)
        if len(part):
            dates = (
                part.index.to_timestamp() if isinstance(part.index, pd.PeriodIndex) else part.index
            )
            if dates.min() < pd.Timestamp(first) or dates.max() > pd.Timestamp(last):
                raise ValueError("EVDS response outside requested dates")
            parts.append(part)
    if not parts:
        raise ValueError("No EVDS observations in requested windows")
    return series.clean(pd.concat(parts))


def evds_windows(start: str, end: str, frequency: str | None) -> list[tuple[str, str]]:
    """Nonoverlapping windows below EVDS's documented 1,000-row backward cap."""
    first, last = pd.Timestamp(start), pd.Timestamp(end)
    if frequency == "monthly":
        if len(pd.period_range(first, last, freq="M")) >= 1000:
            raise ValueError("Monthly EVDS range exceeds row cap")
        return [(start, end)]
    if frequency not in ("daily", "business_daily"):
        raise ValueError("Verified EVDS native frequency required")
    return [
        (
            max(first, pd.Timestamp(year, 1, 1)).date().isoformat(),
            min(last, pd.Timestamp(year + 1, 12, 31)).date().isoformat(),
        )
        for year in range(first.year, last.year + 1, 2)
    ]


def run(root: Path, config_path: Path, *, fetch: bool = True) -> dict:
    config = Config.model_validate(yaml.safe_load(config_path.read_text()))
    keys = read_keys(root / ".env")
    client = Client(root)
    source_file = root / "results/source_checksums.json"
    if not fetch and source_file.exists():
        client.records = json.loads(source_file.read_text())
    began = time.monotonic()
    stamp = datetime.now(ZoneInfo("Europe/Berlin")).strftime("%Y%m%dT%H%M%S%z")
    directory = root / "runs" / f"g1_{stamp}"
    directory.mkdir(parents=True)
    processed = root / "data/processed"
    processed.mkdir(parents=True, exist_ok=True)
    statuses: dict[str, Any] = {}
    monthly_data: dict[str, pd.Series] = {}
    transformed: dict[str, pd.Series] = {}
    for spec in config.series:
        try:
            if fetch:
                values = acquire(client, spec, config, keys)
                values.to_csv(processed / f"{spec.name}_native.csv", header=[spec.name])
            else:
                cached = processed / f"{spec.name}_native.csv"
                if not cached.exists():
                    cached = processed / f"{spec.name}_monthly.csv"
                if not cached.exists():
                    raise AccessError("No processed monthly observations")
                table = pd.read_csv(cached, index_col=0)
                index = (
                    pd.PeriodIndex(table.index, freq="M")
                    if table.index.str.fullmatch(r"\d{4}-\d{2}").all()
                    else pd.DatetimeIndex(table.index)
                )
                values = pd.Series(table.iloc[:, 0].to_numpy(), index=index)
            months, counts = series.monthly(values, config.end)
            months = months.loc[pd.Period(config.start, freq="M") :]
            counts = {month: count for month, count in counts.items() if month >= config.start[:7]}
            # An all-missing provider response is an unavailable series, not a valid panel.
            if not months.notna().any():
                raise ValueError("No observed values in requested range")
            monthly_data[spec.name] = months
            transformed[spec.name] = series.transform(months, spec.transform)
            months.to_csv(processed / f"{spec.name}_monthly.csv", header=[spec.name])
            statuses[spec.name] = {
                "status": "available",
                "spec": spec.model_dump(),
                "native_observed_first": str(values.first_valid_index()),
                "native_observed_last": str(values.last_valid_index()),
                "native_nonmissing": int(values.notna().sum()),
                "native_timestamp_format": "month"
                if isinstance(values.index, pd.PeriodIndex)
                else "date",
                "source_labels": [
                    label
                    for label in client.records
                    if label == spec.name or label.startswith(spec.name + ":")
                ],
                "coverage": coverage(
                    months, "1999-01" if spec.role != "TR" else "2006-01", config.end[:7]
                ),
                "daily_nonmissing_counts": counts,
            }
        except (AccessError, ValueError, KeyError) as error:
            # Do not log raw exceptions: authenticated URLs/data may contain credentials.
            reason = str(error) if isinstance(error, AccessError) else type(error).__name__
            statuses[spec.name] = {
                "status": "blocked" if "Missing" in reason else "failed",
                "reason": reason,
                "spec": spec.model_dump(),
            }
            if reason == "HTTP 429":
                break
    if fetch:
        policy_base = (
            "https://www.tcmb.gov.tr/wps/wcm/connect/EN/TCMB%2BEN/Main%2BMenu/"
            "Core%2BFunctions/Monetary%2BPolicy/Central%2BBank%2BInterest%2BRates/"
        )
        try:
            on = parse_schedule(
                client.get("cbrt_on", policy_base + "CBRT%2BINTEREST%2BRATES"), "Borrowing"
            )
            repo = parse_schedule(
                client.get("cbrt_repo", policy_base + "1%2BWeek%2BRepo"), "Lending"
            )
            effective = announced_rate(on, repo, "2006-01-01", config.end)
            effective.to_csv(processed / "tr_announced_monthly.csv", header=["tr_announced"])
            on.to_csv(processed / "cbrt_on_events.csv", header=["borrowing"])
            repo.to_csv(processed / "cbrt_repo_events.csv", header=["lending"])
            monthly_data["tr_announced"] = transformed["tr_announced"] = effective
            statuses["tr_announced"] = {
                "status": "available",
                "coverage": coverage(effective, "2006-01", config.end[:7]),
                "known_effective_date_hold": True,
                "not_AOFM_substitute": True,
            }
        except (AccessError, ValueError) as error:
            statuses["tr_announced"] = {"status": "failed", "reason": type(error).__name__}
    elif (processed / "tr_announced_monthly.csv").exists():
        table = pd.read_csv(processed / "tr_announced_monthly.csv", index_col=0)
        effective = pd.Series(
            table.iloc[:, 0].to_numpy(), index=pd.PeriodIndex(table.index, freq="M")
        )
        monthly_data["tr_announced"] = transformed["tr_announced"] = effective
        statuses["tr_announced"] = {
            "status": "available",
            "coverage": coverage(effective, "2006-01", config.end[:7]),
            "known_effective_date_hold": True,
            "not_AOFM_substitute": True,
        }
    panel = pd.DataFrame(transformed).sort_index()
    raw_monthly = pd.DataFrame(monthly_data).sort_index()
    raw_monthly.to_csv(processed / "monthly_untransformed.csv")
    panel.to_csv(processed / "baseline_levels.csv")
    # Preserve the documented raw splice AND a spread-adjusted comparator, never
    # replace the approved overnight definition or the ECB two-year baseline.
    if {"ea_eonia", "ea_estr"} <= set(panel.columns):
        panel["ea_overnight"] = panel["ea_eonia"].where(
            panel.index < pd.Period("2019-10"), panel["ea_estr"]
        )
        panel["ea_overnight_adjusted"] = (panel["ea_eonia"] - 0.085).where(
            panel.index < pd.Period("2019-10"), panel["ea_estr"]
        )
        panel.to_csv(processed / "baseline_levels.csv")
    panel.reindex(pd.period_range(panel.index.min(), panel.index.max(), freq="M")).diff().to_csv(
        processed / "robustness_differences.csv"
    )
    ea_columns = ["brent", "vix", "ea_ip", "ea_hicp", "ea_2y", "eurusd"]
    tr_columns = ["brent", "vix", "fedfunds", "tr_ip", "tr_cpi", "tr_aofm", "usdtry"]

    def joint_end(columns: list[str]) -> str:
        ends = [panel[col].last_valid_index() for col in columns if col in panel]
        return (
            str(min(str(end) for end in ends))
            if ends and len(ends) == len(columns)
            else config.end[:7]
        )

    samples = {
        "EA_baseline": panel_sample(
            panel, ea_columns, config.ea_baseline_start, config.ea_baseline_end
        ),
        "EA_overnight_1999_2019": panel_sample(
            panel,
            [x for x in ea_columns if x != "ea_2y"] + ["ea_overnight"],
            config.ea_robustness_start,
            "2019-12",
        ),
        "EA_bundesbank_extension": panel_sample(
            panel,
            [x for x in ea_columns if x != "ea_2y"] + ["de_2y"],
            config.ea_robustness_start,
            config.ea_baseline_end,
        ),
        "TR_target": panel_sample(panel, tr_columns, "2006-01", joint_end(tr_columns)),
    }
    if "tr_aofm" in panel:
        samples["TR_AOFM_observed_history"] = panel_sample(
            panel, tr_columns, str(panel["tr_aofm"].first_valid_index()), joint_end(tr_columns)
        )
    samples["TR_pass_through"] = panel_sample(
        panel, ["tr_cpi", "usdtry", "tr_reer"], "2006-01", joint_end(tr_columns)
    )
    bridge = {
        name: series.price_bridge(monthly_data[old], monthly_data[new])
        for name, old, new in [
            ("headline", "tr_cpi_old", "tr_cpi"),
            ("core_b", "tr_core_b_old", "tr_core_b"),
            ("core_c", "tr_core_c_old", "tr_core_c"),
        ]
        if old in monthly_data and new in monthly_data
    }
    unit_roots = {
        name: diagnostics(
            panel[name].loc[
                pd.Period("2004-09" if name.startswith("ea_") else "2006-01") : pd.Period(
                    config.ea_baseline_end if name.startswith("ea_") else joint_end(tr_columns)
                )
            ]
        )
        for name in transformed
    }
    detail, comparison = supplementary(raw_monthly, joint_end(tr_columns))
    for name, result in detail.items():
        result["bridge_status"] = bridge[name]["status"]
    for name, result in [
        ("price_bridge_detail.json", detail),
        ("policy_comparator_check.json", comparison),
    ]:
        (root / "results" / name).write_text(json.dumps(result, indent=2) + "\n")
    summary = {
        "gate": "G1",
        "run": directory.name,
        "seed": config.seed,
        "status": "blocked"
        if any(s["status"] != "available" for s in statuses.values())
        or samples["EA_baseline"]["status"] != "complete_target"
        or samples.get("TR_AOFM_observed_history", {}).get("status") != "complete_target"
        else "data_checked",
        "series": statuses,
        "samples": samples,
        "price_bridge_checks": bridge,
        "unit_root_diagnostics": unit_roots,
        "baseline": "levels; tests do not choose transforms",
        "fred_route": config.fred_route,
        "paid_calls": 0,
        "elapsed_seconds": time.monotonic() - began,
        "no_estimation_or_identification_run": True,
    }
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    manifest = {
        "run": directory.name,
        "git_commit": commit,
        "git_dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=root)),
        "config": config.model_dump(),
        "sources": client.records,
        "config_sha256": hashlib.sha256(config_path.read_bytes()).hexdigest(),
        "python": platform.python_version(),
        "libraries": {d.metadata["Name"]: d.version for d in distributions() if d.metadata["Name"]},
        "code_sha256": {
            str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted([*(root / "src").rglob("*.py"), *(root / "scripts").rglob("*.py")])
        },
        "processed_sha256": {
            str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(processed.glob("*.csv"))
        },
        "fetch": fetch,
        "verification_sha256": {
            str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for name in [
                "evds_metadata.json",
                "terms_register.json",
                "brief_contract.json",
                "price_bridge_detail.json",
                "policy_comparator_check.json",
            ]
            if (p := root / "results" / name).exists()
        },
    }
    snapshot = directory / "processed"
    snapshot.mkdir()
    for path in processed.glob("*.csv"):
        shutil.copy2(path, snapshot / path.name)
    (directory / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (directory / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    (root / "results/g1_data_checks.json").write_text(json.dumps(summary, indent=2) + "\n")
    if fetch:
        (root / "results/source_checksums.json").write_text(
            json.dumps(client.records, indent=2) + "\n"
        )
    return summary
