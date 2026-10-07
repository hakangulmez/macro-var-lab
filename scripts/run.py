"""Thin CLI for the scaffold smoke check."""

from pathlib import Path

import typer

from macro_var_lab.runtime import run


def main(config: Path = Path("configs/quick.yaml")) -> None:
    typer.echo(run(config, Path.cwd()))


if __name__ == "__main__":
    typer.run(main)
