"""Validated configuration and reproducible run metadata."""

import json
import logging
import platform
import subprocess
from datetime import datetime, timezone
from importlib.metadata import distributions
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict


class RunConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    seed: int
    mode: str


def load_config(path: Path) -> RunConfig:
    return RunConfig.model_validate(yaml.safe_load(path.read_text()))


def run(config_path: Path, root: Path) -> Path:
    config = load_config(config_path)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    directory = root / "runs" / stamp
    directory.mkdir(parents=True)
    logger = logging.getLogger(stamp)
    logger.setLevel(logging.INFO)
    handler = logging.FileHandler(directory / "run.log")
    logger.addHandler(handler)
    versions = {d.metadata["Name"]: d.version for d in distributions() if d.metadata["Name"]}
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=False
    )
    environment = {"python": platform.python_version(), "libraries": versions}
    manifest = {
        "config": config.model_dump(),
        "environment": environment,
        "git_commit": commit.stdout.strip() or None,
        "kind": "scaffold_smoke",
    }
    (directory / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (root / "results").mkdir(exist_ok=True)
    (root / "results" / "environment.json").write_text(json.dumps(environment, indent=2) + "\n")
    logger.info("Scaffold smoke completed; seed=%s; no research or LLM calls", config.seed)
    handler.close()
    logger.removeHandler(handler)
    return directory
