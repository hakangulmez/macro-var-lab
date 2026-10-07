"""Read-only G1 audit. Writes only its aggregate audit result; no fetch or reprocessing."""

import hashlib
import json
import subprocess
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import numpy as np
import pandas as pd
import yaml

from macro_var_lab import series
from macro_var_lab.access import read_keys
from macro_var_lab.policy import parse_schedule

root = Path.cwd()
summary = json.loads((root / "results/g1_data_checks.json").read_text())
run_dir = root / "runs" / summary["run"]
manifest = json.loads((run_dir / "manifest.json").read_text())
config = yaml.safe_load((root / "configs/data.yaml").read_text())
metadata = json.loads((root / "results/evds_metadata.json").read_text())
checks = []


def check(name, passed, detail):
    checks.append({"check": name, "passed": bool(passed), "detail": detail})


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def payload(record):
    path = (
        root / "data/raw/responses" / (hashlib.sha256(record["url"].encode()).hexdigest() + ".bin")
    )
    check("source checksum", sha(path) == record["sha256"], record["url"])
    return path.read_bytes()


def monthly_file(name):
    t = pd.read_csv(root / "data/processed" / name, index_col=0)
    t.index = pd.PeriodIndex(t.index, freq="M")
    return t


def equal(left, right):
    both = pd.concat([left.rename("left"), right.rename("right")], axis=1)
    return both["left"].isna().equals(both["right"].isna()) and np.allclose(
        both["left"].dropna(), both["right"].dropna(), rtol=1e-12, atol=1e-10
    )


check(
    "configuration lineage",
    sha(root / "configs/data.yaml") == manifest["config_sha256"],
    "Pinned selectors, sample dates, native frequencies and FRED API route",
)
for path, expected in manifest["verification_sha256"].items():
    check("verification input lineage", sha(root / path) == expected, path)
for path, expected in manifest["code_sha256"].items():
    check("code lineage", sha(root / path) == expected, path)
for path, expected in manifest["processed_sha256"].items():
    check("processed checksum", sha(root / path) == expected, path)
    snapshot = run_dir / "processed" / Path(path).name
    check(
        "run snapshot checksum",
        snapshot.exists() and sha(snapshot) == expected,
        str(snapshot.relative_to(root)),
    )
levels = monthly_file("baseline_levels.csv")
raw_monthly = monthly_file("monthly_untransformed.csv")
diff = monthly_file("robustness_differences.csv")
for spec in config["series"]:
    name = spec["name"]
    state = summary["series"][name]
    records = [manifest["sources"][label] for label in state["source_labels"]]
    native_parts = []
    for record in records:
        raw = payload(record)
        provider = spec["provider"]
        if provider == "eurostat":
            native = series.eurostat(raw, spec["selectors"])
        elif provider == "ecb":
            native = series.ecb(raw, spec["identifier"])
        elif provider == "bundesbank":
            native = series.bundesbank(raw, spec["identifier"])
        elif provider == "fred":
            identity = parse_qs(urlparse(record["url"]).query).get("series_id")
            check(
                "FRED v1 API identity",
                identity == [spec["identifier"]]
                and urlparse(record["url"]).path == "/fred/series/observations",
                name,
            )
            native = series.fred(raw, spec["identifier"], "api")
        else:
            data = json.loads(raw)
            check("EVDS unsaturated window", len(data["items"]) < 1000, name)
            native = series.evds(raw, spec["identifier"])
        if len(native):
            native_parts.append(native)
    native = pd.concat(native_parts).sort_index()
    check("native uniqueness", not native.index.duplicated().any(), name)
    saved = pd.read_csv(root / "data/processed" / f"{name}_native.csv", index_col=0).iloc[:, 0]
    saved.index = (
        pd.PeriodIndex(saved.index, freq="M")
        if isinstance(native.index, pd.PeriodIndex)
        else pd.DatetimeIndex(saved.index)
    )
    check("raw to native lineage", equal(native, saved), name)
    if isinstance(native.index, pd.PeriodIndex):
        monthly = native.loc[
            pd.Period(config["start"], freq="M") : pd.Period(config["end"], freq="M")
        ]
    else:
        retained = native.loc[pd.Timestamp(config["start"]) : pd.Timestamp(config["end"])]
        monthly = retained.groupby(retained.index.to_period("M")).mean()
        counts = retained.groupby(retained.index.to_period("M")).count()
        check(
            "observed-day counts",
            state["daily_nonmissing_counts"] == {str(m): int(n) for m, n in counts.items()},
            name,
        )
    check("monthly aggregation", equal(monthly, raw_monthly[name]), name)
    expected = monthly.copy()
    if spec["transform"] != "rate":
        expected = np.log(expected) * (100 if spec["transform"] == "log100" else 1)
    check("levels transformation", equal(expected, levels[name]), name)
    target = monthly.reindex(
        pd.period_range(
            state["coverage"]["target_start"], state["coverage"]["target_end"], freq="M"
        )
    )
    missing = [str(m) for m in target.index[target.isna()]]
    check("reported missingness", missing == state["coverage"]["missing_dates"], name)
    if provider == "evds":
        meta = metadata[name]
        row = meta["series"]
        check(
            "EVDS catalogue identity/frequency",
            row["SERIE_CODE"] == spec["identifier"]
            and meta["verified_frequency"] == spec["native_frequency"],
            name,
        )
        catalogue = json.loads(payload(meta["source"]))
        check("EVDS metadata source lineage", row in catalogue, name)
        groups = json.loads(payload(meta["group_source"]))
        check(
            "EVDS group unit lineage",
            any(meta["group"] in cat.get("DATAGROUPS", []) for cat in groups),
            name,
        )
        actual_frequency = "monthly" if isinstance(native.index, pd.PeriodIndex) else "daily"
        check(
            "EVDS native timestamp frequency",
            actual_frequency == ("monthly" if spec["native_frequency"] == "monthly" else "daily"),
            name,
        )

# Independent calendar-day point lookup from the unchanged official schedules.
on = parse_schedule(payload(manifest["sources"]["cbrt_on"]), "Borrowing")
repo = parse_schedule(payload(manifest["sources"]["cbrt_repo"]), "Lending")
dates = pd.date_range("2006-01-01", config["end"], freq="D")
values = []
for date in dates:
    schedule = on if date < pd.Timestamp("2010-05-20") else repo
    values.append(schedule.loc[schedule.index <= date].iloc[-1])
announced = pd.Series(values, index=dates).groupby(dates.to_period("M")).mean()
check(
    "announced policy comparator",
    equal(announced, levels["tr_announced"].reindex(announced.index)),
    "O/N borrowing before 20 May 2010; one-week repo lending thereafter; calendar-day weights",
)
check(
    "policy boundary anchors",
    pd.Timestamp("2010-05-20") in repo.index and pd.Timestamp("2018-06-01") in repo.index,
    "Both change dates verified in official table",
)
for label, adjusted in [("ea_overnight", False), ("ea_overnight_adjusted", True)]:
    expected = (levels["ea_eonia"] - (0.085 if adjusted else 0)).where(
        levels.index < pd.Period("2019-10"), levels["ea_estr"]
    )
    check("overnight composition", equal(expected, levels[label]), label)
expected_diff = levels.reindex(
    pd.period_range(levels.index.min(), levels.index.max(), freq="M")
).diff()
check(
    "differences include comparators and preserve gaps",
    list(diff.columns) == list(expected_diff.columns)
    and all(equal(diff[c], expected_diff[c]) for c in expected_diff),
    "All saved levels columns, including announced rate and separately named overnight comparators",
)
for label, new, old in [
    ("headline", "tr_cpi", "tr_cpi_old"),
    ("core_b", "tr_core_b", "tr_core_b_old"),
    ("core_c", "tr_core_c", "tr_core_c_old"),
]:
    overlap = raw_monthly[[old, new]].dropna()
    ratio = overlap[new] / overlap[old]
    relative_range = ratio.max() / ratio.min() - 1
    bridge = summary["price_bridge_checks"][label]
    check(
        "price bridge",
        len(overlap) == bridge["overlap_months"]
        and np.isclose(relative_range, bridge["ratio_relative_range"])
        and bridge["status"]
        == ("ratio_stable" if relative_range <= 0.002 else "incompatible_rebase")
        and not bridge["automatically_spliced"],
        label,
    )
    detail = json.loads((root / "results/price_bridge_detail.json").read_text())[label]
    gap = (np.log(raw_monthly[new]).diff() - np.log(raw_monthly[old]).diff()) * 100
    check(
        "price growth preservation summary",
        np.isclose(gap.abs().max(), detail["max_abs_monthly_log_growth_gap_pp"])
        and np.isclose(gap.abs().mean(), detail["mean_abs_monthly_log_growth_gap_pp"])
        and detail["bridge_status"] == bridge["status"],
        label,
    )
policy = json.loads((root / "results/policy_comparator_check.json").read_text())
pair = raw_monthly.loc[
    "2006-01" : summary["samples"]["TR_target"]["requested_end"], ["tr_aofm", "tr_announced"]
].dropna()
gap = pair.tr_aofm - pair.tr_announced
check(
    "funding versus announced aggregate comparison",
    len(pair) == policy["overlap_months"]
    and np.isclose(gap.abs().mean(), policy["mean_abs_gap_pp"])
    and np.isclose(gap.abs().max(), policy["max_abs_gap_pp"])
    and not policy["AOFM_substituted"],
    "Indicators are compared over observed common months, never substituted",
)
for name, result in summary["unit_root_diagnostics"].items():
    start = pd.Period("2004-09" if name.startswith("ea_") else "2006-01")
    end = pd.Period(
        config["ea_baseline_end"]
        if name.startswith("ea_")
        else summary["samples"]["TR_target"]["requested_end"]
    )
    observed = levels[name].loc[start:end].notna()
    lengths = []
    current = 0
    for flag in observed:
        current = current + 1 if flag else 0
        lengths.append(current)
    check(
        "diagnostics contiguous input",
        result["observations"] == max(lengths, default=0)
        and not result["baseline_transform_changed"],
        name,
    )
for name, columns in {
    "EA_baseline": ["brent", "vix", "ea_ip", "ea_hicp", "ea_2y", "eurusd"],
    "EA_overnight_1999_2019": ["brent", "vix", "ea_ip", "ea_hicp", "eurusd", "ea_overnight"],
    "EA_bundesbank_extension": ["brent", "vix", "ea_ip", "ea_hicp", "eurusd", "de_2y"],
    "TR_target": ["brent", "vix", "fedfunds", "tr_ip", "tr_cpi", "tr_aofm", "usdtry"],
    "TR_pass_through": ["tr_cpi", "usdtry", "tr_reer"],
    "TR_AOFM_observed_history": [
        "brent",
        "vix",
        "fedfunds",
        "tr_ip",
        "tr_cpi",
        "tr_aofm",
        "usdtry",
    ],
}.items():
    result = summary["samples"][name]
    target = levels[columns].reindex(
        pd.period_range(result["requested_start"], result["requested_end"], freq="M")
    )
    missing = [str(m) for m in target.index[~target.notna().all(axis=1)]]
    check(
        "joint sample missingness",
        missing == result["missing_dates"]
        and len(target) - len(missing) == result["complete_months"],
        name,
    )
check(
    "approved EA contract",
    summary["samples"]["EA_baseline"]["requested_start"] == "2004-09"
    and summary["samples"]["EA_baseline"]["requested_end"] == "2026-07"
    and summary["samples"]["EA_overnight_1999_2019"]["requested_start"] == "1999-12",
    "No sample or indicator substitution",
)
keys = read_keys(root / ".env")
eligible = subprocess.check_output(
    ["git", "ls-files", "-co", "--exclude-standard"], cwd=root, text=True
).splitlines()
leaks = []
paths = (
    {root / p for p in eligible} | set((root / "data").rglob("*")) | set((root / "runs").rglob("*"))
)
for path in paths:
    if path.is_file() and any(value.encode() in path.read_bytes() for value in keys.values()):
        leaks.append(str(path.relative_to(root)))
check(
    "credential byte scan",
    not leaks,
    {
        "files_checked": sum(p.is_file() for p in paths),
        "leaking_paths": leaks,
        "key_presence": {name: True for name in keys},
    },
)
check("local storage", "CloudStorage" not in root.resolve().parts, str(root))
check(
    "no remotes",
    not subprocess.check_output(["git", "remote"], cwd=root, text=True).strip(),
    "No push destination configured",
)
check(
    "private paths ignored",
    all(
        subprocess.run(["git", "check-ignore", "-q", path], cwd=root).returncode == 0
        for path in [
            ".env",
            "data/raw/responses/example.bin",
            "data/processed/example.csv",
            "runs/example/manifest.json",
            ".venv/example",
        ]
    ),
    "Keys, raw/processed data, runs and environments excluded from Git",
)
check(
    "no private files tracked",
    not any(
        p == ".env" or p.startswith(("data/raw/", "data/processed/", "runs/", ".venv/"))
        for p in subprocess.check_output(["git", "ls-files"], cwd=root, text=True).splitlines()
    ),
    "Code/aggregate checks only",
)
check(
    "no G2 or paid run",
    summary["paid_calls"] == 0 and summary["no_estimation_or_identification_run"],
    "G1 retrieval and diagnostics only",
)
result = {
    "gate": "G1",
    "run": summary["run"],
    "read_only_inputs": True,
    "network_calls": 0,
    "checks": checks,
    "passed": sum(c["passed"] for c in checks),
    "failed": sum(not c["passed"] for c in checks),
    "limitations": [
        (
            "Source parsers are shared with the tested pipeline; aggregation, transforms, "
            "calendar weights and missingness are independently recomputed."
        ),
        (
            "No independent replication of every unit-root statistic; contiguous inputs and "
            "unchanged baseline are checked."
        ),
        (
            "Current revised histories, not real-time vintages. Core historical bridge failures "
            "remain; no splice."
        ),
        "TR target lacks AOFM before January 2011; only observed AOFM sample is eligible.",
    ],
}
(root / "results/g1_audit.json").write_text(json.dumps(result, indent=2) + "\n")
print({k: result[k] for k in ["run", "passed", "failed", "network_calls"]})
if result["failed"]:
    print([c for c in checks if not c["passed"]])
    raise SystemExit(1)
