"""Unit tests for appendix builder."""

import pytest
from app.pipeline.appendix import build_latex_appendix, build_text_appendix
from app.models.release import AttachmentModel


class TestBuildLatexAppendix:
    def test_empty_attachments(self):
        assert build_latex_appendix([]) == ""

    def test_appendix_reference(self):
        att = AttachmentModel(label="Migration Script", path="migrate.sql")
        result = build_latex_appendix([att])
        assert r"\appendix" in result
        assert r"\subsection*{Migration Script}" in result
        assert r"\texttt{migrate.sql}" in result

    def test_embed_pdf(self):
        att = AttachmentModel(label="Report", path="report.pdf", type="embed")
        att.resolved_path = "/tmp/report.pdf"
        result = build_latex_appendix([att])
        assert r"\includepdf" in result

    def test_multiple_attachments(self):
        atts = [
            AttachmentModel(label="Script", path="migrate.sql"),
            AttachmentModel(label="Guide", path="guide.txt"),
        ]
        result = build_latex_appendix(atts)
        assert "Script" in result
        assert "Guide" in result

    def test_special_chars_escaped(self):
        att = AttachmentModel(label="Config & Setup", path="config.txt")
        result = build_latex_appendix([att])
        assert r"Config \& Setup" in result


class TestBuildTextAppendix:
    def test_empty_attachments(self):
        assert build_text_appendix([]) == ""

    def test_text_format(self):
        att = AttachmentModel(label="Notes", path="notes.txt")
        result = build_text_appendix([att])
        assert "Appendices" in result
        assert "Notes: notes.txt" in result

    def test_embed_marker(self):
        att = AttachmentModel(label="PDF", path="doc.pdf", type="embed")
        result = build_text_appendix([att])
        assert "embedded" in result.lower()
