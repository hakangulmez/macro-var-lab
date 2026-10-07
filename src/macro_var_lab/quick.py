"""Offline G1 pipeline exercise in an isolated synthetic workspace."""

import json
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from macro_var_lab.data import Config, run
from macro_var_lab.data_figures import write
from macro_var_lab.g2 import run as run_g2
from macro_var_lab.release import run as run_g3


def quick(root: Path) -> dict:
    cache = root / ".cache"
    cache.mkdir(exist_ok=True)
    config_path = root / "configs/data.yaml"
    config = Config.model_validate(yaml.safe_load(config_path.read_text()))
    with tempfile.TemporaryDirectory(prefix="synthetic-g1-", dir=cache) as directory:
        synthetic = Path(directory)
        processed = synthetic / "data/processed"
        processed.mkdir(parents=True)
        (synthetic / "results").mkdir()
        rng = np.random.default_rng(config.seed)
        index = pd.period_range("1999-01", "2010-12", freq="M")
        for spec in config.series:
            values = pd.Series(100 + np.cumsum(rng.normal(0.1, 0.2, len(index))), index=index)
            if spec.transform == "rate":
                values = (values - 100) / 10
            values.to_csv(processed / f"{spec.name}_monthly.csv", header=[spec.name])
        result = run(synthetic, config_path, fetch=False)
        write(synthetic)
        summary = {
            "kind": "synthetic_offline_G1",
            "seed": config.seed,
            "series_checked": len(result["series"]),
            "network_calls": 0,
            "paid_calls": 0,
            "empirical_results_untouched": True,
        }
        # G2 uses a separate complete synthetic history; no real observations or keys.
        index2 = pd.period_range("1998-12", "2026-09", freq="M")
        columns = [s.name for s in config.series] + [
            "tr_announced",
            "ea_overnight",
            "ea_overnight_adjusted",
        ]
        values2 = rng.normal(size=(len(index2), len(columns)))
        for t in range(1, len(values2)):
            values2[t] += 0.5 * values2[t - 1]
        pd.DataFrame(values2 + 100, index=index2, columns=columns).to_csv(
            processed / "baseline_levels.csv"
        )
        (synthetic / "results/g1_data_checks.json").write_text(
            json.dumps({"status": "data_checked", "run": "synthetic_quick"})
        )
        g2_config = yaml.safe_load((root / "configs/g2.yaml").read_text())
        g2_config.update(bootstrap_draws=3, sign_draws=10, horizon=6)
        g2_path = synthetic / "g2.yaml"
        g2_path.write_text(yaml.safe_dump(g2_config))
        (synthetic / "configs").mkdir()
        (synthetic / "configs/g2.yaml").write_text(yaml.safe_dump(g2_config))
        summary["G3"] = {"models": len(run_g3(synthetic, quick=True)["models"])}
        # Git provenance for this temporary exercise comes from the surrounding repo.
        summary["G2"] = {
            "models": len(run_g2(synthetic, g2_path)["models"]),
            "bootstrap_draws": 3,
            "kind": "synthetic_only",
        }
    (cache / "quick_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary
