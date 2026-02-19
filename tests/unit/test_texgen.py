"""Unit tests for LaTeX source generation and escaping."""

import pytest
from app.foxit.texgen import _escape_latex, _build_latex_source


class TestLatexEscaping:
    def test_ampersand(self):
        assert _escape_latex("A & B") == r"A \& B"

    def test_percent(self):
        assert _escape_latex("100%") == r"100\%"

    def test_dollar(self):
        assert _escape_latex("$100") == r"\$100"

    def test_hash(self):
        assert _escape_latex("#1") == r"\#1"

    def test_underscore(self):
        assert _escape_latex("my_var") == r"my\_var"

    def test_braces(self):
        assert _escape_latex("{x}") == r"\{x\}"

    def test_tilde(self):
        assert r"\textasciitilde" in _escape_latex("~")

    def test_caret(self):
        assert r"\textasciicircum" in _escape_latex("^")

    def test_plain_text_unchanged(self):
        assert _escape_latex("Hello World") == "Hello World"

    def test_multiple_specials(self):
        result = _escape_latex("A & B $ C # D")
        assert r"\&" in result
        assert r"\$" in result
        assert r"\#" in result


class TestBuildLatexSource:
    def test_minimal_input(self):
        src = _build_latex_source({"product_name": "Test", "version": "1.0"})
        assert r"\begin{document}" in src
        assert r"\end{document}" in src
        assert "Test" in src
        assert "1.0" in src

    def test_features_table(self):
        src = _build_latex_source({
            "product_name": "Acme",
            "version": "2.0",
            "features": [{"title": "Dashboard", "description": "New analytics"}],
        })
        assert "Dashboard" in src
        assert "New analytics" in src
        assert "tabularx" in src

    def test_empty_features(self):
        src = _build_latex_source({
            "product_name": "Acme",
            "version": "2.0",
            "features": [],
        })
        assert "textit" in src and "None" in src

    def test_fixes_table(self):
        src = _build_latex_source({
            "product_name": "Acme",
            "version": "2.0",
            "fixes": [{"id": "BUG-1", "title": "Crash fix", "description": "Fixed it"}],
        })
        assert "BUG-1" in src
        assert "Crash fix" in src

    def test_breaking_changes(self):
        src = _build_latex_source({
            "product_name": "Acme",
            "version": "2.0",
            "breaking_changes": [{"title": "API removed", "description": "Gone", "migration": "Use v2"}],
        })
        assert "API removed" in src
        assert "Use v2" in src

    def test_links_section(self):
        src = _build_latex_source({
            "product_name": "Acme",
            "version": "2.0",
            "links": [{"label": "Docs", "url": "https://example.com"}],
        })
        assert r"\url{https://example.com}" in src

    def test_special_chars_in_product_name(self):
        src = _build_latex_source({"product_name": "Acme & Co", "version": "1.0"})
        assert r"Acme \& Co" in src

    def test_xcolor_table_option(self):
        src = _build_latex_source({"product_name": "Test", "version": "1.0"})
        assert r"\usepackage[table]{xcolor}" in src

    def test_fancyhdr_present(self):
        src = _build_latex_source({"product_name": "Test", "version": "1.0"})
        assert r"\usepackage{fancyhdr}" in src
