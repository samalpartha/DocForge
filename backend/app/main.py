"""
DocForge CLI — FastAPI Backend

Endpoints:
  POST /v1/generate       — Release JSON → processed PDF (with job metadata)
  POST /v1/image-to-pdf   — Image(s) → PDF via Foxit Services
  POST /v1/verify         — Run 7-check verification on existing PDF
  POST /v1/ocr/extract    — Image/PDF → extracted text
  POST /v1/ocr/structurize — Text → structured release JSON draft
  GET  /v1/templates      — List available templates
  GET  /health            — Health check
  GET  /                  — Landing page
"""

import time
import os
import uuid
from typing import Any

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.errors import DocForgeError
from app.foxit.pipeline import JobOrchestrator
from app.templates.registry import list_templates
from app.utils.logging import logger


app = FastAPI(
    title="DocForge CLI API",
    description=(
        "Generate polished Release Notes PDFs from JSON using "
        "Foxit Document Generation + PDF Services APIs."
    ),
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-DocForge-Job", "X-Pipeline-Duration-Ms", "X-Request-Id"],
)


@app.on_event("startup")
async def _startup_banner():
    from app.core.config import settings
    logger.info("")
    logger.info("╔══════════════════════════════════════════════════╗")
    logger.info("║           DocForge CLI  ·  API Server v2        ║")
    logger.info("╠══════════════════════════════════════════════════╣")
    logger.info("║  POST /v1/generate      → Release Notes PDF     ║")
    logger.info("║  POST /v1/image-to-pdf  → Image → PDF           ║")
    logger.info("║  POST /v1/verify        → PDF verification      ║")
    logger.info("║  POST /v1/ocr/extract   → OCR text extraction   ║")
    logger.info("║  POST /v1/ocr/structurize → Text → JSON draft   ║")
    logger.info("║  GET  /v1/templates     → Template registry     ║")
    logger.info("║  GET  /health           → Health check          ║")
    logger.info("╠══════════════════════════════════════════════════╣")
    logger.info("║  Doc Gen API : %-33s║", settings.docgen.base_url)
    logger.info("║  PDF Svc API : %-33s║", settings.pdf_services.base_url)
    logger.info("║  Credentials : ✓ loaded                         ║")
    logger.info("╚══════════════════════════════════════════════════╝")
    logger.info("")


# ──────────────────────────────────────────────────────────
# Request/Response models
# ──────────────────────────────────────────────────────────

class GenerateRequest(BaseModel):
    data: dict[str, Any] = Field(
        ..., description="Release JSON payload (product_name, version, features, etc.)"
    )
    template_id: str = Field(
        default="product-release",
        description="Template: product-release | security-advisory | api-release",
    )
    watermark: str = Field(
        default="INTERNAL",
        description="Watermark text to stamp on every page",
    )
    password: str | None = Field(
        default=None,
        description="Optional password to lock the PDF",
    )
    engine: str = Field(
        default="docgen",
        description="Rendering engine: 'docgen' (Foxit Doc Gen API) or 'latex' (tectonic)",
    )
    verify: bool = Field(
        default=True,
        description="Run post-processing verification checks",
    )


class StructurizeRequest(BaseModel):
    text: str = Field(..., description="Raw OCR text to structurize into release JSON")


# ──────────────────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "service": "docforge-api", "version": "2.0.0"}


@app.get("/v1/templates")
async def get_templates():
    """List available PDF templates with their metadata."""
    return [t.model_dump() for t in list_templates()]


@app.post(
    "/v1/generate",
    response_class=Response,
    responses={
        200: {"content": {"application/pdf": {}}, "description": "Generated PDF"},
        422: {"description": "Validation error"},
        500: {"description": "Pipeline error"},
    },
)
async def generate_release_notes(req: GenerateRequest, request: Request):
    """
    Accept release JSON, run the full Foxit pipeline, and return a PDF.

    The response includes an X-DocForge-Job header with the full
    JobResult (timings, verification, hashes) as JSON.

    Data handling: No data is stored. Input is processed in memory
    and discarded after the PDF is returned.
    """
    request_id = uuid.uuid4().hex[:12]
    start = time.perf_counter()

    product = req.data.get("product_name", "?")
    version = req.data.get("version", "?")
    logger.info(
        "[%s] POST /v1/generate — %s v%s | engine=%s watermark=%s password=%s verify=%s",
        request_id, product, version, req.engine, req.watermark,
        "yes" if req.password else "no", req.verify,
    )

    try:
        orchestrator = JobOrchestrator(
            release_data=req.data,
            engine=req.engine,
            watermark_text=req.watermark,
            password=req.password,
            template_id=req.template_id,
            verify=req.verify,
        )
        job_result = await orchestrator.run()
        pdf_bytes = orchestrator.ctx.final_pdf

    except DocForgeError as exc:
        logger.warning("[%s] DocForge error: %s", request_id, exc.code)
        raise HTTPException(status_code=422, detail=exc.to_dict())
    except Exception as exc:
        logger.exception("[%s] Pipeline failed", request_id)
        raise HTTPException(status_code=500, detail=str(exc))

    elapsed_ms = (time.perf_counter() - start) * 1000
    logger.info(
        "[%s] Complete — %d bytes in %.0f ms", request_id, len(pdf_bytes), elapsed_ms
    )

    # Serialize job metadata — base64 for header safety, also as trailing JSON endpoint
    import base64
    job_json = job_result.model_dump_json()
    job_b64 = base64.b64encode(job_json.encode()).decode("ascii")

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{job_result.artifact.filename}"',
            "X-Pipeline-Duration-Ms": f"{elapsed_ms:.0f}",
            "X-Request-Id": request_id,
            "X-DocForge-Job": job_b64,
        },
    )


@app.post("/v1/image-to-pdf", response_class=Response)
async def image_to_pdf(
    files: list[UploadFile] = File(..., description="One or more images"),
    watermark: str = "INTERNAL",
    password: str | None = None,
):
    """
    Convert uploaded images into a single PDF, then post-process
    through Foxit PDF Services (watermark, flatten, optional protect).
    """
    from app.pdf.image_to_pdf import images_to_pdf

    request_id = uuid.uuid4().hex[:12]
    logger.info("[%s] POST /v1/image-to-pdf — %d files", request_id, len(files))

    image_list: list[bytes] = []
    for f in files:
        content = await f.read()
        if len(content) > 10 * 1024 * 1024:
            raise HTTPException(status_code=413, detail=f"File {f.filename} exceeds 10MB limit")
        image_list.append(content)

    try:
        base_pdf = await images_to_pdf(image_list)

        # Post-process through Foxit PDF Services
        from app.foxit.pdfservices import PDFServicesClient
        from app.foxit.auth import FoxitCredentials
        from app.core.config import settings

        pdf_creds = FoxitCredentials(
            client_id=settings.pdf_services.client_id,
            client_secret=settings.pdf_services.client_secret,
        )
        client = PDFServicesClient(
            base_url=settings.pdf_services.base_url,
            credentials=pdf_creds,
        )

        doc_id = await client.upload_pdf(base_pdf, "images.pdf")
        doc_id = await client.add_watermark(document_id=doc_id, text=watermark)
        doc_id = await client.flatten_pdf(doc_id)
        if password:
            doc_id = await client.protect_pdf(document_id=doc_id, user_password=password)
        final_pdf = await client.download_pdf(doc_id)

    except Exception as exc:
        logger.exception("[%s] image-to-pdf failed", request_id)
        raise HTTPException(status_code=500, detail=str(exc))

    return Response(
        content=final_pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": 'attachment; filename="images-converted.pdf"',
            "X-Request-Id": request_id,
        },
    )


@app.post("/v1/verify")
async def verify_pdf(
    file: UploadFile = File(..., description="PDF file to verify"),
    watermark_text: str = "INTERNAL",
    should_be_encrypted: str = "false",
):
    """
    Run 7-check verification on an uploaded PDF.
    Returns detailed check results and content hash.
    """
    from app.pdf.verify import PDFVerifier, VerifyExpectations

    request_id = uuid.uuid4().hex[:12]
    logger.info("[%s] POST /v1/verify — %s", request_id, file.filename)

    content = await file.read()
    if len(content) > 50 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File exceeds 50MB limit")

    try:
        expectations = VerifyExpectations(
            watermark_text=watermark_text,
            should_be_encrypted=should_be_encrypted.lower() == "true",
        )
        verifier = PDFVerifier()
        result = verifier.verify(content, expectations)
    except Exception as exc:
        logger.exception("[%s] Verification failed", request_id)
        raise HTTPException(status_code=500, detail=str(exc))

    return result.model_dump()


@app.post("/v1/ocr/extract")
async def ocr_extract(file: UploadFile = File(..., description="Image or PDF to OCR")):
    """
    Extract text from an uploaded image or scanned PDF using OCR.

    Returns structured blocks with per-line confidence scores.
    """
    from app.ocr.extract import extract_from_image, extract_from_pdf

    request_id = uuid.uuid4().hex[:12]
    logger.info("[%s] POST /v1/ocr/extract — %s", request_id, file.filename)

    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File exceeds 10MB limit")

    try:
        content_type = file.content_type or ""
        if "pdf" in content_type or (file.filename and file.filename.lower().endswith(".pdf")):
            result = extract_from_pdf(content)
        else:
            result = extract_from_image(content)
    except Exception as exc:
        logger.exception("[%s] OCR extraction failed", request_id)
        raise HTTPException(status_code=500, detail=str(exc))

    return {
        "raw_text": result.raw_text,
        "blocks": [
            {
                "text": b.text,
                "confidence": round(b.confidence, 3),
                "line_num": b.line_num,
            }
            for b in result.blocks
        ],
        "overall_confidence": round(result.overall_confidence, 3),
        "page_count": result.page_count,
        "method": result.method,
    }


@app.post("/v1/ocr/structurize")
async def ocr_structurize(req: StructurizeRequest):
    """
    Convert raw text into a structured release JSON draft.

    Returns the draft with confidence scores and quality warnings.
    The user should review and edit before generating a PDF.
    """
    from app.ocr.extract import OCRResult
    from app.ocr.structurize import structurize

    request_id = uuid.uuid4().hex[:12]
    logger.info("[%s] POST /v1/ocr/structurize — %d chars", request_id, len(req.text))

    fake_ocr = OCRResult(
        raw_text=req.text,
        overall_confidence=0.85,
        page_count=1,
        method="manual",
    )

    try:
        result = structurize(fake_ocr)
    except Exception as exc:
        logger.exception("[%s] Structurize failed", request_id)
        raise HTTPException(status_code=500, detail=str(exc))

    return {
        "draft_json": result.draft_json,
        "confidence": round(result.confidence, 3),
        "missing_required": result.missing_required,
        "warnings": result.warnings,
        "needs_review": result.needs_review,
    }


# ──────────────────────────────────────────────────────────
# Landing page (mounted LAST so it doesn't override API routes)
# ──────────────────────────────────────────────────────────

# Static Files (Frontend)
# Try multiple paths to accommodate local and Docker environments
_docs_candidates = [
    os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "docs")),  # Local
    os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "docs")),        # Docker
    os.path.join(os.getcwd(), "docs"),                                             # Root-relative
]

_docs_dir = None
for candidate in _docs_candidates:
    if os.path.isdir(candidate):
        _docs_dir = candidate
        break

if _docs_dir:
    logger.info("  Frontend found at: %s", _docs_dir)
    app.mount("/", StaticFiles(directory=_docs_dir, html=True), name="landing")
else:
    logger.warning("  Frontend not found. Root will return 404.")
