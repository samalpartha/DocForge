"""Unit tests for Pydantic data models."""

import pytest
from app.models.release import (
    ReleaseModel, FeatureModel, FixModel,
    BreakingChangeModel, LinkModel, ImageModel, AttachmentModel,
)
from app.models.job import JobResult, StepTiming, ArtifactMetadata, VerificationResult, DiffSummary, JobState


class TestReleaseModel:
    def test_minimal_valid(self):
        m = ReleaseModel(product_name="Acme", version="1.0.0")
        assert m.product_name == "Acme"
        assert m.version == "1.0.0"
        assert m.features == []
        assert m.fixes == []

    def test_full_model(self):
        m = ReleaseModel(
            product_name="Acme Platform",
            version="2.4.0",
            summary="Major release.",
            features=[FeatureModel(title="Dashboard", description="New analytics dashboard")],
            fixes=[FixModel(id="BUG-101", title="Login fix")],
            breaking_changes=[BreakingChangeModel(title="API v1 removal", description="Removed", migration="Use v2")],
            links=[LinkModel(label="Docs", url="https://docs.example.com")],
        )
        assert len(m.features) == 1
        assert len(m.fixes) == 1
        assert len(m.breaking_changes) == 1

    def test_missing_product_name_fails(self):
        with pytest.raises(Exception):
            ReleaseModel(version="1.0.0")

    def test_missing_version_fails(self):
        with pytest.raises(Exception):
            ReleaseModel(product_name="Acme")

    def test_empty_product_name_fails(self):
        with pytest.raises(Exception):
            ReleaseModel(product_name="", version="1.0.0")

    def test_to_legacy_dict(self):
        m = ReleaseModel(product_name="Acme", version="1.0.0")
        d = m.to_legacy_dict()
        assert d["product_name"] == "Acme"
        assert isinstance(d, dict)

    def test_image_model_defaults(self):
        img = ImageModel(path="screenshot.png")
        assert img.width_percent == 80
        assert img.placement == "inline"
        assert img.resolved_path is None

    def test_attachment_model_defaults(self):
        att = AttachmentModel(label="Script", path="migrate.sql")
        assert att.type == "appendix"


class TestJobResult:
    def test_minimal_job_result(self):
        jr = JobResult(
            job_id="abc123",
            engine_used="latex",
            artifact=ArtifactMetadata(filename="test.pdf", size_bytes=1000),
        )
        assert jr.job_id == "abc123"
        assert jr.timings == []
        assert jr.verification is None

    def test_full_job_result(self):
        jr = JobResult(
            job_id="xyz789",
            engine_used="docgen",
            input_hash="sha256abc",
            artifact=ArtifactMetadata(filename="out.pdf", size_bytes=5000, pages=2, content_hash="hash123"),
            timings=[StepTiming(step="validate", duration_ms=5, status="ok")],
            verification=VerificationResult(checks_passed=7, checks_total=7, passed=True),
            diff_summary=DiffSummary(watermark_applied=True, size_change_bytes=200),
        )
        assert jr.verification.passed is True
        assert len(jr.timings) == 1

    def test_job_states(self):
        assert JobState.RECEIVED == "RECEIVED"
        assert JobState.FAILED == "FAILED"
        assert JobState.DELIVERED == "DELIVERED"

    def test_step_timing_defaults(self):
        st = StepTiming(step="test", duration_ms=10)
        assert st.status == "ok"
        assert st.detail == ""


class TestVerificationResult:
    def test_defaults(self):
        vr = VerificationResult()
        assert vr.passed is False
        assert vr.checks_passed == 0

    def test_all_passed(self):
        vr = VerificationResult(
            page_count=1, has_text=True,
            watermark_detected=True, watermark_on_all_pages=True,
            is_encrypted=False, flattening_signals=True,
            checks_passed=7, checks_total=7, passed=True,
            content_hash="abc123",
        )
        assert vr.passed is True
