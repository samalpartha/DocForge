"""Unit tests for the structured error catalog."""

import pytest
from app.errors import (
    DocForgeError, ValidationError, AssetNotFoundError,
    AssetPathTraversalError, AssetTooLargeError, AssetTypeBlockedError,
    EngineError, LatexCompileError, LatexTimeoutError,
    FoxitAPIError, VerificationFailedError,
    OCRLowConfidenceError, OCRExtractionError,
)


class TestErrorCatalog:
    """Verify all 12 error types have correct codes and serialization."""

    def test_base_error(self):
        e = DocForgeError(code="TEST", message="test msg", suggestion="try this")
        d = e.to_dict()
        assert d["error_code"] == "TEST"
        assert d["message"] == "test msg"
        assert d["suggestion"] == "try this"

    def test_validation_error(self):
        e = ValidationError(errors=["missing product_name"])
        assert e.code == "VALIDATION_FAILED"
        assert "product_name" in e.message
        d = e.to_dict()
        assert d["detail"] == ["missing product_name"]

    def test_asset_not_found(self):
        e = AssetNotFoundError("images/missing.png")
        assert e.code == "ASSET_NOT_FOUND"
        assert "missing.png" in e.message

    def test_asset_path_traversal(self):
        e = AssetPathTraversalError("../../etc/passwd")
        assert e.code == "ASSET_PATH_TRAVERSAL"

    def test_asset_too_large(self):
        e = AssetTooLargeError("big.png", 15.0, 10.0)
        assert e.code == "ASSET_TOO_LARGE"
        assert "10" in e.message

    def test_asset_type_blocked(self):
        e = AssetTypeBlockedError("script.exe", ".exe")
        assert e.code == "ASSET_TYPE_BLOCKED"
        assert ".exe" in e.message

    def test_engine_error(self):
        e = EngineError("docgen", "Template invalid")
        assert e.code == "DOCGEN_ERROR"

    def test_latex_compile_error(self):
        e = LatexCompileError("Undefined control sequence")
        assert e.code == "LATEX_COMPILE_FAILED"

    def test_latex_timeout(self):
        e = LatexTimeoutError(60)
        assert e.code == "LATEX_TIMEOUT"
        assert "60" in e.message

    def test_foxit_api_error(self):
        e = FoxitAPIError("Doc Gen", 401, "Unauthorized")
        assert e.code == "FOXIT_DOC_GEN_ERROR"
        assert "401" in e.message

    def test_verification_failed(self):
        e = VerificationFailedError(5, 7, ["watermark", "encryption"])
        assert e.code == "VERIFICATION_FAILED"
        assert "5/7" in e.message

    def test_ocr_low_confidence(self):
        e = OCRLowConfidenceError(0.45, 0.70)
        assert e.code == "OCR_LOW_CONFIDENCE"

    def test_ocr_extraction_error(self):
        e = OCRExtractionError("No sections found")
        assert e.code == "OCR_EXTRACTION_FAILED"

    def test_all_errors_are_exceptions(self):
        """Every error in the catalog must be a subclass of Exception."""
        error_classes = [
            ValidationError, AssetNotFoundError, AssetPathTraversalError,
            AssetTooLargeError, AssetTypeBlockedError, EngineError,
            LatexCompileError, LatexTimeoutError, FoxitAPIError,
            VerificationFailedError, OCRLowConfidenceError, OCRExtractionError,
        ]
        for cls in error_classes:
            assert issubclass(cls, DocForgeError)
            assert issubclass(cls, Exception)

    def test_error_count(self):
        """Ensure all 12 error types are accounted for."""
        error_classes = [
            ValidationError, AssetNotFoundError, AssetPathTraversalError,
            AssetTooLargeError, AssetTypeBlockedError, EngineError,
            LatexCompileError, LatexTimeoutError, FoxitAPIError,
            VerificationFailedError, OCRLowConfidenceError, OCRExtractionError,
        ]
        assert len(error_classes) == 12
