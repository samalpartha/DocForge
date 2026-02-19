"""
DocForge — Structured error catalog.

Every error has a code, human message, and suggested fix.
No raw exceptions leak to the frontend.
"""

from __future__ import annotations

from typing import Any


class DocForgeError(Exception):
    """Base error with structured code + suggestion."""

    def __init__(self, code: str, message: str, suggestion: str = "", detail: Any = None):
        self.code = code
        self.message = message
        self.suggestion = suggestion
        self.detail = detail
        super().__init__(message)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "error_code": self.code,
            "message": self.message,
        }
        if self.suggestion:
            d["suggestion"] = self.suggestion
        if self.detail:
            d["detail"] = self.detail
        return d


class ValidationError(DocForgeError):
    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__(
            code="VALIDATION_FAILED",
            message=f"Input validation failed: {'; '.join(errors)}",
            suggestion="Check required fields: product_name (string), version (string).",
            detail=errors,
        )


class AssetNotFoundError(DocForgeError):
    def __init__(self, path: str):
        super().__init__(
            code="ASSET_NOT_FOUND",
            message=f"Asset file not found: {path}",
            suggestion="Check the path in images[] or attachments[]. Paths must be relative to the assets directory.",
        )


class AssetPathTraversalError(DocForgeError):
    def __init__(self, path: str):
        super().__init__(
            code="ASSET_PATH_TRAVERSAL",
            message=f"Path traversal blocked: {path}",
            suggestion="Use relative paths only. '..' is not allowed.",
        )


class AssetTooLargeError(DocForgeError):
    def __init__(self, path: str, size_mb: float, limit_mb: float):
        super().__init__(
            code="ASSET_TOO_LARGE",
            message=f"File exceeds {limit_mb}MB limit: {path} ({size_mb:.1f}MB)",
            suggestion="Compress or resize the file before uploading.",
        )


class AssetTypeBlockedError(DocForgeError):
    def __init__(self, path: str, ext: str):
        super().__init__(
            code="ASSET_TYPE_BLOCKED",
            message=f"File type not allowed: {ext} ({path})",
            suggestion="Allowed types: jpg, jpeg, png, gif, pdf, txt.",
        )


class EngineError(DocForgeError):
    def __init__(self, engine: str, message: str, suggestion: str = ""):
        super().__init__(
            code=f"{engine.upper()}_ERROR",
            message=message,
            suggestion=suggestion or f"Check the {engine} engine configuration.",
        )


class LatexCompileError(DocForgeError):
    def __init__(self, message: str):
        super().__init__(
            code="LATEX_COMPILE_FAILED",
            message=f"LaTeX compilation failed: {message}",
            suggestion="Check your template for syntax errors. See the compile output for details.",
        )


class LatexTimeoutError(DocForgeError):
    def __init__(self, timeout_s: int):
        super().__init__(
            code="LATEX_TIMEOUT",
            message=f"LaTeX compilation timed out after {timeout_s}s",
            suggestion="Simplify the template or remove complex macros.",
        )


class FoxitAPIError(DocForgeError):
    def __init__(self, api: str, status: int, body: str = ""):
        super().__init__(
            code=f"FOXIT_{api.upper().replace(' ', '_')}_ERROR",
            message=f"Foxit {api} returned HTTP {status}",
            suggestion="Check your Foxit API credentials and the input format.",
            detail=body[:500] if body else None,
        )


class VerificationFailedError(DocForgeError):
    def __init__(self, checks_passed: int, checks_total: int, failures: list[str]):
        super().__init__(
            code="VERIFICATION_FAILED",
            message=f"PDF verification: {checks_passed}/{checks_total} checks passed",
            suggestion="Retry generation or check the pipeline configuration.",
            detail=failures,
        )


class OCRLowConfidenceError(DocForgeError):
    def __init__(self, confidence: float, threshold: float):
        super().__init__(
            code="OCR_LOW_CONFIDENCE",
            message=f"OCR confidence {confidence:.0%} is below threshold {threshold:.0%}",
            suggestion="Upload a clearer image or manually review the extracted text.",
        )


class OCRExtractionError(DocForgeError):
    def __init__(self, message: str):
        super().__init__(
            code="OCR_EXTRACTION_FAILED",
            message=f"Could not extract structured data: {message}",
            suggestion="Review and edit the draft JSON manually before generating.",
        )
