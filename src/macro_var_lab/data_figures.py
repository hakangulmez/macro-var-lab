"""Private descriptive QA plots, never mistaken for estimated policy responses."""

import json
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from macro_var_lab.viz import apply_style, export


def write(root: Path) -> None:
    summary = json.loads((root / "results/g1_data_checks.json").read_text())
    frame = pd.read_csv(root / "data/processed/baseline_levels.csv", index_col=0)
    frame.index = pd.PeriodIndex(frame.index, freq="M")
    columns = list(frame.columns)
    if not columns:
        return
    apply_style()
    destination = root / "data/processed/check_plots"
    figure, axes = plt.subplots(
        (len(columns) + 2) // 3, 3, figsize=(15, 3 * ((len(columns) + 2) // 3)), squeeze=False
    )
    for axis, name in zip(axes.flat, columns, strict=False):
        values = frame[name]
        axis.plot(pd.PeriodIndex(values.index, freq="M").to_timestamp(), values, linewidth=1)
        axis.set_title(name, fontsize=10)
        axis.tick_params(labelsize=8)
    for axis in list(axes.flat)[len(columns) :]:
        axis.set_visible(False)
    figure.suptitle("G1 data checks: descriptive series, no policy-shock estimates")
    figure.tight_layout(rect=(0, 0.045, 1, 0.96))
    export(
        figure,
        destination / "levels_overview",
        "Sources: Eurostat, ECB, Deutsche Bundesbank, FRED/original providers; "
        "author's monthly aggregation/log transforms. Observations, no inferential bands.",
    )
    plt.close(figure)
    ea = frame[["ea_2y", "de_2y", "ea_eonia", "ea_estr"]]
    figure, axis = plt.subplots(figsize=(10, 5))
    for column in ea:
        axis.plot(pd.PeriodIndex(ea.index, freq="M").to_timestamp(), ea[column], label=column)
    axis.set_ylabel("Percent / percentage-point levels")
    axis.set_title("G1 policy indicators: definitions differ; no silent substitution")
    axis.legend()
    export(
        figure,
        destination / "policy_indicators",
        "Source: ECB; Source: Deutsche Bundesbank. Author's observed-day monthly means. "
        "Descriptive series; no inference.",
    )
    plt.close(figure)
    (destination / "plot_manifest.json").write_text(
        json.dumps(
            {
                "kind": "private_data_QA",
                "run": summary["run"],
                "not_IRFs_or_results": True,
                "raw_series_figures_not_in_git": True,
                "series_count": len(columns),
            },
            indent=2,
        )
        + "\n"
    )
