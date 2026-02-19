"""
DocForge — Job result and pipeline output contracts.

Every generation returns a JobResult with full traceability:
timings, hashes, verification results, and artifact metadata.
"""

from __future__ import annotations

import enum
from typing import Any

from pydantic import BaseModel, Field


class JobState(str, enum.Enum):
    RECEIVED = "RECEIVED"
    VALIDATED = "VALIDATED"
    ASSET_RESOLVED = "ASSET_RESOLVED"
    BASE_PDF_GENERATED = "BASE_PDF_GENERATED"
    POST_PROCESSED = "POST_PROCESSED"
    VERIFIED = "VERIFIED"
    DELIVERED = "DELIVERED"
    FAILED = "FAILED"


class StepTiming(BaseModel):
    step: str
    duration_ms: int
    status: str = "ok"  # ok | skipped | failed
    detail: str = ""


class ArtifactMetadata(BaseModel):
    filename: str
    size_bytes: int
    pages: int = 0
    content_hash: str = ""  # SHA-256 of final PDF


class VerificationResult(BaseModel):
    page_count: int = 0
    has_text: bool = False
    watermark_detected: bool = False
    watermark_on_all_pages: bool = False
    is_encrypted: bool = False
    flattening_signals: bool = False
    file_size: int = 0
    content_hash: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    checks_passed: int = 0
    checks_total: int = 0
    passed: bool = False

    class Config:
        json_schema_extra = {
            "example": {
                "page_count": 1,
                "has_text": True,
                "watermark_detected": True,
                "watermark_on_all_pages": True,
                "is_encrypted": False,
                "flattening_signals": True,
                "checks_passed": 7,
                "checks_total": 7,
                "passed": True,
            }
        }


class DiffSummary(BaseModel):
    watermark_applied: bool = False
    flattened: bool = False
    password_protected: bool = False
    size_change_bytes: int = 0


class JobResult(BaseModel):
    """Complete output contract for every PDF generation job."""

    job_id: str
    engine_used: str
    input_hash: str = ""  # SHA-256 of input JSON
    artifact: ArtifactMetadata
    before_pdf_id: str | None = None
    after_pdf_id: str | None = None
    timings: list[StepTiming] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    verification: VerificationResult | None = None
    diff_summary: DiffSummary | None = None
