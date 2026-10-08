# ruff: noqa: E501
"""Two-page employer note; all empirical text supplied by the result renderer."""

from pathlib import Path

from reportlab.lib.colors import HexColor
from reportlab.lib.utils import ImageReader, simpleSplit
from reportlab.pdfgen import canvas


def write_note(
    root: Path,
    title,
    question,
    method,
    findings,
    limitations,
    technical,
    sources,
    subtitle=None,
    secondary_figure=None,
):
    assert len(findings) == 3 and len(limitations) <= 5
    c = canvas.Canvas(str(root / "report/policy_note.pdf"), pagesize=(595.28, 841.89))
    c.setTitle(title)
    c.setAuthor("Hakan Zeki Gulmez")

    def paragraph(text, y, size=11, width=511, x=42):
        text = text.replace("–", "-").replace("×", "x")
        c.setFont("Helvetica", size)
        for line in simpleSplit(text, "Helvetica", size, width):
            c.drawString(x, y, line)
            y -= size * 1.45
        return y - 12

    def header(label):
        c.setFillColor(HexColor("#0072B2"))
        c.rect(42, 786, 511, 3, fill=1, stroke=0)
        c.setFillColor(HexColor("#172B3A"))
        paragraph(label, 758, 18)
        paragraph("Hakan Zeki Gulmez | Research brief | 7 October 2026", 716, 9)
        if subtitle:
            paragraph(subtitle, 695, 10)

    def footer(page):
        c.setFillColor(HexColor("#555555"))
        paragraph(f"Research brief | {page}/2", 35, 8)
        c.setFillColor(HexColor("#172B3A"))

    header(title)
    y = paragraph("Question", 673, 12)
    y = paragraph(question, y)
    y = paragraph("Method", y, 12)
    y = paragraph(method, y)
    c.drawImage(
        ImageReader(str(root / "figures/headline.png")),
        42,
        155,
        width=511,
        height=340,
        preserveAspectRatio=True,
        anchor="c",
    )
    paragraph(sources, 113, 8)
    footer(1)
    c.showPage()
    header("Three findings for the decision-maker")
    y = 666
    for i, finding in enumerate(findings, 1):
        y = paragraph(f"{i}. {finding}", y, 11 if secondary_figure else 12)
        if not secondary_figure:
            y -= 18
    if secondary_figure:
        c.drawImage(
            ImageReader(str(root / secondary_figure)),
            72,
            y - 195,
            width=451,
            height=190,
            preserveAspectRatio=True,
            anchor="c",
        )
        y -= 207
    # Short, bounded limitations box, not a second technical paper.
    box_top = y + 8
    box_bottom = y - 30 - 26 * len(limitations)
    c.setFillColor(HexColor("#F1F5F8"))
    c.rect(36, box_bottom, 523, box_top - box_bottom, fill=1, stroke=0)
    c.setFillColor(HexColor("#172B3A"))
    y = paragraph("Limitations", y - 8, 12)
    for limitation in limitations:
        y = paragraph("- " + limitation, y, 9.5) - 1
    paragraph(
        "Detailed assumptions, diagnostics and source lineage: the technical working paper and docs/PROVENANCE.md.",
        min(y - 15, box_bottom - 20),
        9,
    )
    footer(2)
    c.save()
    text = (
        "# "
        + title
        + "\n\n"
        + question
        + "\n\n"
        + method
        + "\n\n![Headline](../figures/headline.png)\n\n"
    )
    text += "\n".join("- " + f for f in findings)
    if secondary_figure:
        text += "\n\n![Türkiye price responses](../" + secondary_figure + ")\n"
    text += "\n\n## Limitations\n\n" + "\n".join("- " + f for f in limitations)
    text += "\n\n## Technical notes\n\n" + technical + "\n\n" + sources + "\n"
    (root / "report/report.md").write_text(text)
    return technical
