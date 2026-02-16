"""
DocForge CLI — FastAPI Backend

Single endpoint:
  POST /v1/generate
    Body: { "data": { ... release JSON ... }, "watermark": "INTERNAL", "password": null }
    Response: application/pdf bytes
"""

import time
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.foxit.pipeline import run_pipeline
from app.utils.logging import logger
from app.utils.validate import ValidationError


app = FastAPI(
    title="DocForge CLI API",
    description=(
        "Generate polished Release Notes PDFs from JSON using "
        "Foxit Document Generation + PDF Services APIs."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def _startup_banner():
    from app.core.config import settings
    logger.info("")
    logger.info("╔══════════════════════════════════════════════════╗")
    logger.info("║           DocForge CLI  ·  API Server           ║")
    logger.info("╠══════════════════════════════════════════════════╣")
    logger.info("║  POST /v1/generate   → Release Notes PDF        ║")
    logger.info("║  GET  /health        → Health check             ║")
    logger.info("╠══════════════════════════════════════════════════╣")
    logger.info("║  Doc Gen API : %-33s║", settings.docgen.base_url)
    logger.info("║  PDF Svc API : %-33s║", settings.pdf_services.base_url)
    logger.info("║  Credentials : ✓ loaded                         ║")
    logger.info("╚══════════════════════════════════════════════════╝")
    logger.info("")


class GenerateRequest(BaseModel):
    data: dict[str, Any] = Field(
        ..., description="Release JSON payload (product_name, version, features, etc.)"
    )
    template_id: str = Field(
        default="release-notes-v1",
        description="Template identifier (reserved for future use)",
    )
    watermark: str = Field(
        default="INTERNAL",
        description="Watermark text to stamp on every page",
    )
    password: str | None = Field(
        default=None,
        description="Optional password to lock the PDF",
    )


@app.get("/health")
async def health():
    return {"status": "ok", "service": "docforge-api"}


@app.post(
    "/v1/generate",
    response_class=Response,
    responses={
        200: {"content": {"application/pdf": {}}, "description": "Generated PDF"},
        422: {"description": "Validation error"},
        500: {"description": "Pipeline error"},
    },
)
async def generate_release_notes(req: GenerateRequest):
    """
    Accept release JSON, run the full Foxit pipeline, and return a PDF.
    """
    start = time.perf_counter()

    try:
        pdf_bytes = await run_pipeline(
            release_data=req.data,
            watermark_text=req.watermark,
            password=req.password,
        )
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail={"errors": exc.errors})
    except Exception as exc:
        logger.exception("Pipeline failed")
        raise HTTPException(status_code=500, detail=str(exc))

    elapsed_ms = (time.perf_counter() - start) * 1000
    logger.info("Total request time: %.0f ms", elapsed_ms)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": "attachment; filename=release-notes.pdf",
            "X-Pipeline-Duration-Ms": f"{elapsed_ms:.0f}",
        },
    )
