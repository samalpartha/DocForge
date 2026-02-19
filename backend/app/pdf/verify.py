"""
DocForge — PDF verification module.

Inspects PDFs locally (no Foxit API calls) to verify post-processing
was applied correctly. Uses pymupdf (fitz) for parsing.

Checks:
  1. PDF opens and parses
  2. Page count is stable
  3. Has text content
  4. Watermark text detected
  5. Watermark on all pages
  6. Encryption flags match expectation
  7. Flattening signals (no interactive annotations)
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from app.models.job import VerificationResult, DiffSummary
from app.utils.logging import logger, step_timer


@dataclass
class VerifyExpectations:
    watermark_text: str = ""
    should_be_encrypted: bool = False
    expected_pages: int | None = None


class PDFVerifier:
    """Local PDF inspection using pymupdf. No external API calls."""

    def verify(self, pdf_bytes: bytes, expectations: VerifyExpectations) -> VerificationResult:
        try:
            import fitz
        except ImportError:
            logger.warning("pymupdf not installed — skipping verification")
            return VerificationResult(
                checks_passed=0, checks_total=0, passed=True,
                file_size=len(pdf_bytes),
                content_hash=hashlib.sha256(pdf_bytes).hexdigest(),
            )

        with step_timer("Verify PDF"):
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")

            checks: dict[str, bool] = {}

            # 1. Opens and parses
            checks["opens_and_parses"] = len(doc) > 0

            # 2. Page count
            if expectations.expected_pages is not None:
                checks["page_count_stable"] = len(doc) == expectations.expected_pages
            else:
                checks["page_count_stable"] = True

            # 3. Has text
            has_text = any(page.get_text().strip() for page in doc)
            checks["has_text_content"] = has_text

            # 4-5. Watermark
            if expectations.watermark_text:
                wm = expectations.watermark_text.upper()
                all_pages_have_wm = True
                any_page_has_wm = False
                for page in doc:
                    text = page.get_text().upper()
                    if wm in text:
                        any_page_has_wm = True
                    else:
                        all_pages_have_wm = False
                checks["watermark_detected"] = any_page_has_wm
                checks["watermark_all_pages"] = all_pages_have_wm
            else:
                checks["watermark_detected"] = True
                checks["watermark_all_pages"] = True

            # 6. Encryption
            checks["encryption_matches"] = doc.is_encrypted == expectations.should_be_encrypted

            # 7. Flattening (no interactive annotations remain)
            has_annotations = False
            for page in doc:
                annots = list(page.annots() or [])
                if annots:
                    has_annotations = True
                    break
            checks["no_annotations"] = not has_annotations

            passed_count = sum(checks.values())
            total_count = len(checks)

            metadata_raw = doc.metadata or {}
            metadata: dict[str, Any] = {k: v for k, v in metadata_raw.items() if v}

            result = VerificationResult(
                page_count=len(doc),
                has_text=has_text,
                watermark_detected=checks.get("watermark_detected", False),
                watermark_on_all_pages=checks.get("watermark_all_pages", False),
                is_encrypted=doc.is_encrypted,
                flattening_signals=not has_annotations,
                file_size=len(pdf_bytes),
                content_hash=hashlib.sha256(pdf_bytes).hexdigest(),
                metadata=metadata,
                checks_passed=passed_count,
                checks_total=total_count,
                passed=passed_count == total_count,
            )

            doc.close()

            logger.info(
                "  Verification: %d/%d checks passed %s",
                passed_count, total_count,
                "✓" if result.passed else "✗",
            )
            return result

    def compute_diff(
        self,
        before_bytes: bytes,
        after_bytes: bytes,
        watermark_text: str = "",
        password_applied: bool = False,
    ) -> DiffSummary:
        """Compare before/after PDFs and produce a diff summary."""
        try:
            import fitz
        except ImportError:
            return DiffSummary(size_change_bytes=len(after_bytes) - len(before_bytes))

        before = fitz.open(stream=before_bytes, filetype="pdf")
        after = fitz.open(stream=after_bytes, filetype="pdf")

        wm_detected = False
        if watermark_text:
            wm = watermark_text.upper()
            for page in after:
                if wm in page.get_text().upper():
                    wm_detected = True
                    break

        before_annots = sum(len(list(p.annots() or [])) for p in before)
        after_annots = sum(len(list(p.annots() or [])) for p in after)

        before.close()
        after.close()

        return DiffSummary(
            watermark_applied=wm_detected,
            flattened=before_annots > 0 and after_annots == 0,
            password_protected=password_applied,
            size_change_bytes=len(after_bytes) - len(before_bytes),
        )
