from pathlib import Path

import matplotlib.pyplot as plt
import pytest
from pydantic import ValidationError

from macro_var_lab.runtime import load_config, run
from macro_var_lab.viz import apply_style, export


def test_run_metadata(tmp_path: Path) -> None:
    config = tmp_path / "config.yaml"
    config.write_text("seed: 42\nmode: scaffold\n")
    assert load_config(config).seed == 42
    directory = run(config, tmp_path)
    assert (directory / "manifest.json").is_file()
    assert (directory / "run.log").is_file()
    assert (tmp_path / "results/environment.json").is_file()


def test_reject_unknown_config(tmp_path: Path) -> None:
    config = tmp_path / "bad.yaml"
    config.write_text("seed: 42\nmode: scaffold\nunknown: 1\n")
    with pytest.raises(ValidationError):
        load_config(config)


def test_publication_exports(tmp_path: Path) -> None:
    apply_style()
    figure, axis = plt.subplots()
    axis.set_xlabel("Synthetic fixture")
    axis.set_ylabel("Synthetic fixture")
    export(figure, tmp_path / "fixture", "Source: test fixture; no empirical result")
    assert (tmp_path / "fixture.png").is_file()
    assert (tmp_path / "fixture.pdf").is_file()
    plt.close(figure)
