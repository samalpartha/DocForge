"""
DocForge CLI — Job Orchestrator (Pipeline v2).

Runs the full PDF generation pipeline as a state machine:

  RECEIVED → VALIDATED → ASSET_RESOLVED → BASE_PDF_GENERATED
  → POST_PROCESSED → VERIFIED → DELIVERED

Each step is timed, logged, and recorded in the JobResult.
The pipeline remains synchronous for hackathon simplicity but
is structured for future async worker support.
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.errors import DocForgeError, ValidationError
from app.foxit.auth import FoxitCredentials
from app.models.job import (
    ArtifactMetadata,
    DiffSummary,
    JobResult,
    JobState,
    StepTiming,
    VerificationResult,
)
from app.models.release import ReleaseModel
from app.pdf.verify import PDFVerifier, VerifyExpectations
from app.pipeline.resolve_assets import resolve_assets
from app.utils.logging import logger


class PipelineContext:
    """Mutable context passed through pipeline steps."""

    def __init__(self):
        self.release: ReleaseModel | None = None
        self.base_pdf: bytes = b""
        self.base_pdf_doc_id: str | None = None
        self.final_pdf: bytes = b""
        self.final_pdf_doc_id: str | None = None
        self.warnings: list[str] = []


class JobOrchestrator:
    """
    State-machine orchestrator for the PDF generation pipeline.

    Tracks every step's timing and status. Produces a complete
    JobResult with verification data and content hashes.
    """

    def __init__(
        self,
        release_data: dict[str, Any],
        engine: str = "docgen",
        watermark_text: str = "INTERNAL",
        password: str | None = None,
        template_id: str = "product-release",
        asset_dir: str | None = None,
        verify: bool = True,
    ):
        self.job_id = uuid.uuid4().hex[:12]
        self.engine = engine
        self.watermark_text = watermark_text
        self.password = password
        self.template_id = template_id
        self.asset_dir = asset_dir
        self.verify = verify
        self.raw_data = release_data
        self.state = JobState.RECEIVED
        self.ctx = PipelineContext()
        self.timings: list[StepTiming] = []

    def _record_step(self, name: str, start: float, status: str = "ok", detail: str = ""):
        ms = int((time.perf_counter() - start) * 1000)
        self.timings.append(StepTiming(step=name, duration_ms=ms, status=status, detail=detail))
        symbol = "✓" if status == "ok" else ("⊘" if status == "skipped" else "✗")
        logger.info("  %s %s — %dms %s", symbol, name, ms, detail)

    async def run(self) -> JobResult:
        """Execute the full pipeline. Returns a complete JobResult."""
        logger.info("=" * 60)
        logger.info("[%s] Pipeline starting (engine=%s)", self.job_id, self.engine)
        logger.info("=" * 60)
        pipeline_start = time.perf_counter()

        try:
            await self._step_validate()
            await self._step_resolve_assets()
            await self._step_generate()
            await self._step_post_process()

            verification = None
            diff = None
            if self.verify:
                verification, diff = await self._step_verify()

            self.state = JobState.DELIVERED

        except DocForgeError:
            self.state = JobState.FAILED
            raise
        except Exception:
            self.state = JobState.FAILED
            raise

        input_hash = hashlib.sha256(
            json.dumps(self.raw_data, sort_keys=True).encode()
        ).hexdigest()

        content_hash = hashlib.sha256(self.ctx.final_pdf).hexdigest()

        # Count pages
        pages = 0
        try:
            import fitz
            doc = fitz.open(stream=self.ctx.final_pdf, filetype="pdf")
            pages = len(doc)
            doc.close()
        except Exception:
            pass

        product = self.raw_data.get("product_name", "unknown")
        version = self.raw_data.get("version", "0.0.0")
        
        # Sanitise product name for filename (ASCII only)
        safe_product = product.lower().replace(" ", "-")
        import re
        safe_product = re.sub(r"[^a-z0-9\-_]", "", safe_product)
        
        filename = f"{safe_product}-v{version}-release-notes.pdf"

        total_ms = int((time.perf_counter() - pipeline_start) * 1000)
        logger.info("=" * 60)
        logger.info(
            "[%s] Pipeline complete — %d bytes, %d pages, %dms",
            self.job_id, len(self.ctx.final_pdf), pages, total_ms,
        )
        logger.info("=" * 60)

        return JobResult(
            job_id=self.job_id,
            engine_used=self.engine,
            input_hash=input_hash,
            artifact=ArtifactMetadata(
                filename=filename,
                size_bytes=len(self.ctx.final_pdf),
                pages=pages,
                content_hash=content_hash,
            ),
            before_pdf_id=self.ctx.base_pdf_doc_id,
            after_pdf_id=self.ctx.final_pdf_doc_id,
            timings=self.timings,
            warnings=self.ctx.warnings,
            verification=verification,
            diff_summary=diff,
        )

    async def _step_validate(self):
        t = time.perf_counter()
        try:
            self.ctx.release = ReleaseModel(**self.raw_data)
            self.state = JobState.VALIDATED
            logger.info(
                "  Product: %s v%s",
                self.ctx.release.product_name, self.ctx.release.version,
            )
            self._record_step("validate", t)
        except Exception as exc:
            self._record_step("validate", t, "failed", str(exc))
            errors = [str(exc)]
            raise ValidationError(errors)

    async def _step_resolve_assets(self):
        t = time.perf_counter()
        if not self.ctx.release.images and not self.ctx.release.attachments:
            self._record_step("resolve_assets", t, "skipped", "no assets")
            self.state = JobState.ASSET_RESOLVED
            return

        asset_path = Path(self.asset_dir) if self.asset_dir else None
        warnings = resolve_assets(self.ctx.release, asset_path)
        self.ctx.warnings.extend(warnings)
        self.state = JobState.ASSET_RESOLVED
        self._record_step("resolve_assets", t)

    async def _step_generate(self):
        t = time.perf_counter()
        data = self.ctx.release.to_legacy_dict()

        if self.engine == "latex":
            from app.foxit.texgen import generate_pdf_from_latex
            self.ctx.base_pdf = await generate_pdf_from_latex(release_data=data)
        else:
            from app.foxit.docgen import generate_pdf_from_template
            docgen_creds = FoxitCredentials(
                client_id=settings.docgen.client_id,
                client_secret=settings.docgen.client_secret,
            )
            self.ctx.base_pdf = await generate_pdf_from_template(
                base_url=settings.docgen.base_url,
                credentials=docgen_creds,
                release_data=data,
            )

        self.state = JobState.BASE_PDF_GENERATED
        self._record_step("generate", t, detail=f"{self.engine} → {len(self.ctx.base_pdf)} bytes")

    async def _step_post_process(self):
        from app.foxit.pdfservices import PDFServicesClient

        t = time.perf_counter()
        pdf_creds = FoxitCredentials(
            client_id=settings.pdf_services.client_id,
            client_secret=settings.pdf_services.client_secret,
        )
        client = PDFServicesClient(
            base_url=settings.pdf_services.base_url,
            credentials=pdf_creds,
            poll_interval=settings.poll_interval,
            poll_timeout=settings.poll_timeout,
        )

        doc_id = await client.upload_pdf(self.ctx.base_pdf, "release-notes.pdf")
        self.ctx.base_pdf_doc_id = doc_id

        doc_id = await client.add_watermark(document_id=doc_id, text=self.watermark_text)
        doc_id = await client.flatten_pdf(doc_id)

        if self.password:
            doc_id = await client.protect_pdf(document_id=doc_id, user_password=self.password)

        self.ctx.final_pdf = await client.download_pdf(doc_id)
        self.ctx.final_pdf_doc_id = doc_id
        self.state = JobState.POST_PROCESSED
        self._record_step("post_process", t, detail=f"watermark={self.watermark_text} password={'yes' if self.password else 'no'}")

    async def _step_verify(self) -> tuple[VerificationResult, DiffSummary]:
        t = time.perf_counter()
        verifier = PDFVerifier()

        expectations = VerifyExpectations(
            watermark_text=self.watermark_text,
            should_be_encrypted=bool(self.password),
        )

        verification = verifier.verify(self.ctx.final_pdf, expectations)
        diff = verifier.compute_diff(
            self.ctx.base_pdf,
            self.ctx.final_pdf,
            watermark_text=self.watermark_text,
            password_applied=bool(self.password),
        )

        self.state = JobState.VERIFIED
        self._record_step(
            "verify", t,
            detail=f"{verification.checks_passed}/{verification.checks_total} checks",
        )
        return verification, diff


# Backward-compatible wrapper for the old API
async def run_pipeline(
    release_data: dict[str, Any],
    watermark_text: str = "INTERNAL",
    password: str | None = None,
    engine: str = "docgen",
) -> bytes:
    """Legacy wrapper — returns just the PDF bytes."""
    orchestrator = JobOrchestrator(
        release_data=release_data,
        engine=engine,
        watermark_text=watermark_text,
        password=password,
        verify=False,
    )
    await orchestrator.run()
    return orchestrator.ctx.final_pdf
