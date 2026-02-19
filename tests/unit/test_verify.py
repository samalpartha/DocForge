"""Unit tests for PDF verification module."""

import pytest
from app.pdf.verify import PDFVerifier, VerifyExpectations
from app.models.job import DiffSummary


class TestPDFVerifier:
    """Tests that use pymupdf to create minimal PDFs for verification."""

    @pytest.fixture
    def verifier(self):
        return PDFVerifier()

    @pytest.fixture
    def simple_pdf(self):
        """Create a minimal valid PDF with text."""
        try:
            import fitz
        except ImportError:
            pytest.skip("pymupdf not installed")
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72), "Hello World", fontsize=12)
        pdf_bytes = doc.tobytes()
        doc.close()
        return pdf_bytes

    @pytest.fixture
    def watermarked_pdf(self):
        """Create a PDF with watermark-like text."""
        try:
            import fitz
        except ImportError:
            pytest.skip("pymupdf not installed")
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72), "Hello World", fontsize=12)
        page.insert_text((200, 400), "INTERNAL", fontsize=48)
        pdf_bytes = doc.tobytes()
        doc.close()
        return pdf_bytes

    def test_simple_pdf_opens(self, verifier, simple_pdf):
        result = verifier.verify(simple_pdf, VerifyExpectations())
        assert result.page_count == 1
        assert result.has_text is True
        assert result.checks_passed > 0

    def test_has_content_hash(self, verifier, simple_pdf):
        result = verifier.verify(simple_pdf, VerifyExpectations())
        assert len(result.content_hash) == 64

    def test_watermark_detected(self, verifier, watermarked_pdf):
        result = verifier.verify(
            watermarked_pdf,
            VerifyExpectations(watermark_text="INTERNAL"),
        )
        assert result.watermark_detected is True
        assert result.watermark_on_all_pages is True

    def test_watermark_not_found(self, verifier, simple_pdf):
        result = verifier.verify(
            simple_pdf,
            VerifyExpectations(watermark_text="DRAFT"),
        )
        assert result.watermark_detected is False

    def test_not_encrypted(self, verifier, simple_pdf):
        result = verifier.verify(
            simple_pdf,
            VerifyExpectations(should_be_encrypted=False),
        )
        assert result.is_encrypted is False

    def test_flattened(self, verifier, simple_pdf):
        result = verifier.verify(simple_pdf, VerifyExpectations())
        assert result.flattening_signals is True


class TestComputeDiff:
    @pytest.fixture
    def verifier(self):
        return PDFVerifier()

    @pytest.fixture
    def two_pdfs(self):
        try:
            import fitz
        except ImportError:
            pytest.skip("pymupdf not installed")

        doc1 = fitz.open()
        p1 = doc1.new_page()
        p1.insert_text((72, 72), "Before", fontsize=12)
        before = doc1.tobytes()
        doc1.close()

        doc2 = fitz.open()
        p2 = doc2.new_page()
        p2.insert_text((72, 72), "After INTERNAL", fontsize=12)
        after = doc2.tobytes()
        doc2.close()

        return before, after

    def test_diff_size_change(self, verifier, two_pdfs):
        before, after = two_pdfs
        diff = verifier.compute_diff(before, after)
        assert isinstance(diff.size_change_bytes, int)

    def test_diff_watermark_detected(self, verifier, two_pdfs):
        before, after = two_pdfs
        diff = verifier.compute_diff(before, after, watermark_text="INTERNAL")
        assert diff.watermark_applied is True
