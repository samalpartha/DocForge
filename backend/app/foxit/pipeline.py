"""
DocForge CLI — End-to-end document generation pipeline.

Pipeline steps:
  1. Validate input JSON
  2. Generate base PDF via Foxit Document Generation API
  3. Upload PDF to Foxit PDF Services
  4. Add "INTERNAL" / "DRAFT" watermark
  5. Flatten the PDF
  6. Password-protect the PDF (optional — must be last)
  7. Download final PDF

Each step is logged with its duration.
"""

from typing import Any

from app.core.config import settings
from app.foxit.auth import FoxitCredentials
from app.foxit.docgen import generate_pdf_from_template
from app.foxit.pdfservices import PDFServicesClient
from app.utils.logging import logger, step_timer
from app.utils.validate import validate_release_payload


async def run_pipeline(
    release_data: dict[str, Any],
    watermark_text: str = "INTERNAL",
    password: str | None = None,
) -> bytes:
    """
    Execute the full generate → enhance → deliver pipeline.
    Returns the final PDF as bytes.
    """
    logger.info("=" * 60)
    logger.info("DocForge Pipeline — starting")
    logger.info("=" * 60)

    # --- Step 1: Validate ---
    with step_timer("Step 1 · Validate input"):
        validated = validate_release_payload(release_data)
        logger.info(
            "  Product: %s v%s", validated["product_name"], validated["version"]
        )

    # --- Step 2: Document Generation API ---
    docgen_creds = FoxitCredentials(
        client_id=settings.docgen.client_id,
        client_secret=settings.docgen.client_secret,
    )

    with step_timer("Step 2 · Generate base PDF (Document Generation API)"):
        base_pdf = await generate_pdf_from_template(
            base_url=settings.docgen.base_url,
            credentials=docgen_creds,
            release_data=validated,
        )

    # --- Step 3-6: PDF Services API post-processing ---
    pdf_creds = FoxitCredentials(
        client_id=settings.pdf_services.client_id,
        client_secret=settings.pdf_services.client_secret,
    )
    pdf_client = PDFServicesClient(
        base_url=settings.pdf_services.base_url,
        credentials=pdf_creds,
        poll_interval=settings.poll_interval,
        poll_timeout=settings.poll_timeout,
    )

    # Step 3: Upload
    doc_id = await pdf_client.upload_pdf(base_pdf, "release-notes.pdf")

    # Step 4: Watermark
    doc_id = await pdf_client.add_watermark(
        document_id=doc_id,
        text=watermark_text,
    )

    # Step 5: Flatten (must happen before password-protect)
    doc_id = await pdf_client.flatten_pdf(doc_id)

    # Step 6: Password-protect (optional — last step before download)
    if password:
        doc_id = await pdf_client.protect_pdf(
            document_id=doc_id,
            user_password=password,
        )

    # Step 7: Download
    final_pdf = await pdf_client.download_pdf(doc_id)

    logger.info("=" * 60)
    logger.info("DocForge Pipeline — complete  (%d bytes)", len(final_pdf))
    logger.info("=" * 60)

    return final_pdf
