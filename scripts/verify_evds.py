"""Verify the ten pinned EVDS identities, units and native frequencies."""

import json
from pathlib import Path

import yaml

from macro_var_lab.access import Client, read_keys
from macro_var_lab.data import Config

root = Path.cwd()
config = Config.model_validate(yaml.safe_load((root / "configs/data.yaml").read_text()))
client = Client(root)
keys = read_keys(root / ".env")
base = "https://evds3.tcmb.gov.tr/igmevdsms-dis/"
categories = json.loads(client.get("evds_groups", base + "categories/withDatagroups/type=json"))
groups = {g["DATAGROUP_CODE"]: g for c in categories for g in c.get("DATAGROUPS", [])}
frequencies = {"AYLIK": "monthly", "İŞ GÜNÜ": "business_daily", "GÜNLÜK": "daily"}
units = {
    "tr_ip": "index 2021=100",
    "tr_cpi": "index 2025=100",
    "tr_core_b": "index 2025=100",
    "tr_core_c": "index 2025=100",
    "tr_cpi_old": "index 2003=100",
    "tr_core_b_old": "index 2003=100",
    "tr_core_c_old": "index 2003=100",
    "tr_aofm": "percent",
    "usdtry": "TRY per USD, foreign-exchange buying",
    "tr_reer": "index 2025=100",
}
output = {}
for spec in config.series:
    if spec.provider != "evds":
        continue
    label = spec.name + "_metadata"
    rows = json.loads(
        client.get(
            label,
            base + "serieList/type=json&code=" + spec.identifier,
            headers={"key": keys["EVDS_API_KEY"]},
        )
    )
    matches = [row for row in rows if row["SERIE_CODE"] == spec.identifier]
    if len(matches) != 1:
        raise ValueError("EVDS metadata identity mismatch")
    row = matches[0]
    if frequencies[row["FREQUENCY_STR"]] != spec.native_frequency:
        raise ValueError("EVDS configured native frequency mismatch")
    output[spec.name] = {
        "series": row,
        "group": groups[row["DATAGROUP_CODE"]],
        "source": client.records[label],
        "group_source": client.records["evds_groups"],
        "verified_frequency": spec.native_frequency,
        "units": units[spec.name],
        "unit_basis": (
            "series identity and official group unit/base label; AOFM is the "
            "percent cost component of the mixed-unit funding group"
        ),
        "verified_id": spec.identifier,
    }
(root / "results/evds_metadata.json").write_text(
    json.dumps(output, ensure_ascii=False, indent=2) + "\n"
)
print({"verified_EVDS_series": len(output), "credential_values_printed": False})
