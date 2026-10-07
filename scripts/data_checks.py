"""Offline reconstruction of G1 from private processed monthly observations."""

from pathlib import Path

from macro_var_lab.data import run
from macro_var_lab.data_figures import write

if __name__ == "__main__":
    result = run(Path.cwd(), Path("configs/data.yaml"), fetch=False)
    write(Path.cwd())
    print({"gate": "G1", "status": result["status"], "network_calls": 0})
