"""
DocForge — Appendix builder.

Generates appendix content from attachment references.
Supports LaTeX format for the latex engine and plain-text
summaries for the docgen engine.
"""

from __future__ import annotations

from app.models.release import AttachmentModel
from app.utils.logging import logger


def _escape_latex(text: str) -> str:
    """Minimal LaTeX escaping for appendix content."""
    for ch, rep in [("&", r"\&"), ("%", r"\%"), ("$", r"\$"), ("#", r"\#"),
                    ("_", r"\_"), ("{", r"\{"), ("}", r"\}")]:
        text = text.replace(ch, rep)
    return text


def build_latex_appendix(attachments: list[AttachmentModel]) -> str:
    """
    Build LaTeX appendix section from resolved attachments.

    For 'embed' type PDFs, uses \\includepdf to inline the file.
    For 'appendix' type, generates a reference listing.
    """
    if not attachments:
        return ""

    sections: list[str] = []
    sections.append(r"\newpage")
    sections.append(r"\appendix")
    sections.append(r"\section*{Appendices}")
    sections.append("")

    for att in attachments:
        label = _escape_latex(att.label)
        path = att.resolved_path or att.path

        if att.type == "embed" and path.lower().endswith(".pdf"):
            sections.append(rf"\subsection*{{{label}}}")
            sections.append(rf"\includepdf[pages=-]{{{path}}}")
        else:
            sections.append(rf"\subsection*{{{label}}}")
            safe_path = _escape_latex(att.path)
            sections.append(rf"See attached file: \texttt{{{safe_path}}}")

        sections.append("")

    logger.info("  Built appendix with %d attachments", len(attachments))
    return "\n".join(sections)


def build_text_appendix(attachments: list[AttachmentModel]) -> str:
    """
    Build plain-text appendix listing for docgen engine.
    Returns content suitable for adding to a Word template section.
    """
    if not attachments:
        return ""

    lines = ["Appendices", "=" * 40, ""]
    for att in attachments:
        lines.append(f"- {att.label}: {att.path}")
        if att.type == "embed":
            lines.append("  (embedded document)")
        lines.append("")

    return "\n".join(lines)
