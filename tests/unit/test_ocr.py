"""Unit tests for OCR text structurizer."""

import pytest
from app.ocr.extract import OCRResult
from app.ocr.structurize import (
    structurize, _extract_product_name, _extract_version,
    _extract_date, _split_sections, _extract_list_items,
    _extract_fix_items, _extract_breaking_items,
)


class TestExtractProductName:
    def test_first_line(self):
        assert _extract_product_name("Acme Platform\nv2.4.0") == "Acme Platform"

    def test_skips_version_line(self):
        name = _extract_product_name("v2.4.0\nAcme Platform\nSummary")
        assert name == "Acme Platform"

    def test_skips_release_notes_header(self):
        name = _extract_product_name("Release Notes\nAcme Platform\nv1.0")
        assert name == "Acme Platform"

    def test_empty_text(self):
        assert _extract_product_name("") == ""


class TestExtractVersion:
    def test_semver(self):
        assert _extract_version("Acme v2.4.0") == "2.4.0"

    def test_version_with_prefix(self):
        assert _extract_version("Version 3.1.0") == "3.1.0"

    def test_prerelease(self):
        assert _extract_version("v1.0.0-beta.1") == "1.0.0-beta.1"

    def test_no_version(self):
        assert _extract_version("No version here") == ""


class TestExtractDate:
    def test_iso_date(self):
        assert _extract_date("Released on 2026-02-15") == "2026-02-15"

    def test_slash_date(self):
        assert _extract_date("Date: 2026/01/30") == "2026-01-30"

    def test_no_date(self):
        assert _extract_date("No date") == ""


class TestSplitSections:
    def test_features_section(self):
        text = "Preamble\nNew Features\n- Dashboard\n- Charts"
        sections = _split_sections(text)
        assert "features" in sections
        assert "Dashboard" in sections["features"]

    def test_bug_fixes_section(self):
        text = "Intro\nBug Fixes\n- Fixed crash\n- Fixed login"
        sections = _split_sections(text)
        assert "fixes" in sections

    def test_breaking_changes_section(self):
        text = "Intro\nBreaking Changes\n- Removed API v1"
        sections = _split_sections(text)
        assert "breaking" in sections

    def test_no_sections(self):
        text = "Just some plain text"
        sections = _split_sections(text)
        assert "preamble" in sections


class TestExtractListItems:
    def test_bullet_items(self):
        text = "- Dashboard: New analytics\n- Charts: Real-time"
        items = _extract_list_items(text)
        assert len(items) == 2
        assert items[0]["title"] == "Dashboard"

    def test_numbered_items(self):
        text = "1. First item\n2. Second item"
        items = _extract_list_items(text)
        assert len(items) == 2

    def test_empty_text(self):
        assert _extract_list_items("") == []


class TestExtractFixItems:
    def test_with_bug_ids(self):
        text = "- BUG-101: Fixed crash\n- BUG-102: Login issue"
        items = _extract_fix_items(text)
        assert items[0]["id"] == "BUG-101"

    def test_without_ids(self):
        text = "- Fixed crash on startup"
        items = _extract_fix_items(text)
        assert items[0]["id"] == "FIX-001"


class TestExtractBreakingItems:
    def test_with_migration_hint(self):
        text = "- Removed API v1: migrate to v2 endpoints"
        items = _extract_breaking_items(text)
        assert len(items) == 1
        assert "migrate" in items[0]["migration"].lower()


class TestStructurize:
    def test_full_document(self):
        text = """Acme Platform v2.4.0
Released 2026-02-15

New Features
- Dashboard: Real-time analytics
- API Gateway: Rate limiting

Bug Fixes
- BUG-101: Fixed crash on startup

Breaking Changes
- Removed legacy API: migrate to v2
"""
        ocr = OCRResult(raw_text=text, overall_confidence=0.95, page_count=1, method="test")
        result = structurize(ocr)
        assert result.draft_json["product_name"] == "Acme Platform"
        assert result.draft_json["version"] == "2.4.0"
        assert len(result.draft_json["features"]) == 2
        assert len(result.draft_json["fixes"]) == 1
        assert len(result.draft_json["breaking_changes"]) == 1

    def test_low_confidence_needs_review(self):
        ocr = OCRResult(raw_text="garbled text", overall_confidence=0.4, page_count=1, method="test")
        result = structurize(ocr)
        assert result.needs_review is True

    def test_missing_fields_detected(self):
        ocr = OCRResult(raw_text="No product name or version here", overall_confidence=0.9, page_count=1, method="test")
        result = structurize(ocr)
        assert "product_name" in result.missing_required or "version" in result.missing_required
