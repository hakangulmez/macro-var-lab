"""Compile a result-bound working paper; never acquire data or estimate models."""

import csv as csv_io
import hashlib
import json
import os
import re
import runpy
import shutil
import subprocess
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "report/technical"
GEN = DOC / "generated"
INPUTS = {}
VALUES = {}


def escape(value):
    text = str(value)
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
    }
    rendered = "".join(replacements.get(c, c) for c in text)
    if "_" in text or (len(text) > 28 and "." in text):
        rendered = rendered.replace(".", r".\allowbreak{}").replace(r"\_", r"\_\allowbreak{}")
    return rendered


def csv(name):
    path = ROOT / "results" / name
    INPUTS[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return pd.read_csv(path)


def js(name):
    path = ROOT / "results" / name
    INPUTS[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    result = json.loads(path.read_text())
    if name == "technical_model_contract.json":
        for record in result["source"]:
            actual = hashlib.sha256((ROOT / record["path"]).read_bytes()).hexdigest()
            if actual != record["sha256"]:
                raise RuntimeError(
                    "Implementation changed; re-audit the paper contract: " + record["path"]
                )
    return result


def fmt(value, digits=3):
    return "--" if pd.isna(value) else f"{float(value):.{digits}f}"


def macro(name, value, digits=None):
    rendered = fmt(value, digits) if digits is not None else escape(value)
    VALUES[name] = {"value": value, "rendered": rendered}
    return "\\" + name + "{}"


def table(name, headers, rows, caption, note, layout=None, size="small"):
    if name in {"lags", "roots", "residuals", "computation", "bridge"}:
        size = "footnotesize"
    with (GEN / (name + ".csv")).open("w", newline="") as stream:
        writer = csv_io.writer(stream, lineterminator="\n")
        writer.writerow(headers)
        writer.writerows(rows)
    with (GEN / (name + ".csv")).open() as stream:
        records = list(csv_io.reader(stream))
    headers, rows = records[0], records[1:]
    layout = layout or "X" + "r" * (len(headers) - 1)
    lines = [
        r"\begin{table}[htbp]",
        r"\centering",
        f"\\{size}",
        r"\caption{" + escape(caption) + "}",
        r"\begin{tabularx}{\linewidth}{" + layout + "}",
        r"\toprule",
        " & ".join(escape(x) for x in headers) + r" \\",
        r"\midrule",
    ]
    for row in rows:
        lines.append(" & ".join(escape(x) for x in row) + r" \\")
    lines += [
        r"\bottomrule",
        r"\end{tabularx}",
        r"\par\vspace{3pt}\begin{minipage}{\linewidth}\footnotesize "
        + escape(note)
        + r"\end{minipage}",
        r"\end{table}",
    ]
    (GEN / (name + ".tex")).write_text("\n".join(lines) + "\n")


def main():
    GEN.mkdir(parents=True, exist_ok=True)
    runpy.run_path(str(DOC / "tables.py"))["generate"](csv, js, macro, table, fmt)
    (GEN / "numbers.tex").write_text(
        "% Generated exclusively from result files.\n"
        + "\n".join("\\newcommand{\\" + k + "}{" + v["rendered"] + "}" for k, v in VALUES.items())
        + "\n"
    )
    figure_names = re.findall(r"\\fig\{([^}]+)\}", (DOC / "paper.tex").read_text())
    for name in figure_names:
        path = ROOT / "figures" / name
        INPUTS[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    # Provenance is deliberately relative and includes no raw observations or credentials.
    lineage = {
        "inputs": INPUTS,
        "prose_macros": VALUES,
        "estimation": False,
        "paid_calls": 0,
        "source": "empirical result aggregates; presentation only",
    }
    (GEN / "lineage.json").write_text(json.dumps(lineage, indent=2) + "\n")
    compiler = os.environ.get("TECTONIC") or shutil.which("tectonic")
    if not compiler:
        for path in [ROOT / ".tools/tectonic/tectonic", ROOT.parent / ".tools/tectonic/tectonic"]:
            if path.is_file():
                compiler = str(path)
                break
    if not compiler:
        raise SystemExit(
            (
                "Install the official Tectonic 0.17.0 executable locally, or set "
                "TECTONIC=/absolute/path/tectonic. See report/technical/README.md."
            )
        )
    output = ROOT / ".cache/technical"
    output.mkdir(parents=True, exist_ok=True)
    offline = ["--only-cached"] if os.environ.get("REPORT_OFFLINE") == "1" else []
    subprocess.run(
        [compiler, *offline, "--keep-logs", "--outdir", str(output), "main.tex"],
        cwd=DOC,
        check=True,
    )
    for name, expected in INPUTS.items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != expected:
            raise RuntimeError("Results changed during report build: " + name)
    shutil.copyfile(output / "main.pdf", ROOT / "report/technical_report.pdf")
    print("Working paper built from unchanged result files: report/technical_report.pdf")


if __name__ == "__main__":
    main()
