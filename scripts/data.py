"""Download approved free series; a blocked G1 returns exit status 2."""

from pathlib import Path

from macro_var_lab.data import run
from macro_var_lab.data_figures import write

if __name__ == "__main__":
    summary = run(Path.cwd(), Path("configs/data.yaml"))
    write(Path.cwd())
    print({"gate": "G1", "status": summary["status"], "run": summary["run"]})
    raise SystemExit(2 if summary["status"] == "blocked" else 0)
