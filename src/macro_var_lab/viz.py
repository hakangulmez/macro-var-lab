"""Shared publication plotting style; captions must state source and uncertainty."""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402

PALETTE = ["#0072B2", "#E69F00", "#009E73", "#D55E00", "#CC79A7", "#56B4E9"]


def apply_style() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 11,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.prop_cycle": plt.cycler(color=PALETTE),
        }
    )


def export(figure: Figure, destination: Path, source: str) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    figure.text(0.01, 0.01, source, fontsize=8)
    figure.savefig(destination.with_suffix(".png"), dpi=300, bbox_inches="tight")
    figure.savefig(destination.with_suffix(".pdf"), bbox_inches="tight")
