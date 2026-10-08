import sys
from pathlib import Path

from macro_var_lab.v3_comparison import run

if __name__ == "__main__":
    run(Path(__file__).resolve().parents[1], sys.argv[1] if len(sys.argv) > 1 else "2004-09")
