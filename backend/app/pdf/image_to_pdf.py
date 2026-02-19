"""
DocForge — Image to PDF converter.

Converts one or more images into a single PDF document.
Each image becomes one page, normalised to A4 dimensions.
The resulting PDF is then processed through Foxit PDF Services.
"""

from __future__ import annotations

from app.utils.logging import logger, step_timer


async def images_to_pdf(image_list: list[bytes], page_size: str = "A4") -> bytes:
    """
    Convert a list of image byte arrays into a single PDF.

    Each image is placed on its own page, centered and scaled to fit.
    Returns the raw PDF bytes.
    """
    try:
        import fitz
    except ImportError:
        raise RuntimeError("pymupdf is required for image-to-PDF conversion. pip install pymupdf")

    with step_timer("Convert images → PDF"):
        # A4 dimensions in points (72 dpi)
        page_w, page_h = (595.28, 841.89) if page_size == "A4" else (612, 792)

        doc = fitz.open()

        for i, img_bytes in enumerate(image_list):
            page = doc.new_page(width=page_w, height=page_h)

            # Calculate scaled rect to fit image with margins
            margin = 36  # 0.5 inch
            avail_w = page_w - 2 * margin
            avail_h = page_h - 2 * margin

            # Detect image dimensions
            try:
                img_doc = fitz.open(stream=img_bytes, filetype="png")
                img_page = img_doc[0]
                iw, ih = img_page.rect.width, img_page.rect.height
                img_doc.close()
            except Exception:
                iw, ih = avail_w, avail_h

            # Scale to fit
            scale = min(avail_w / max(iw, 1), avail_h / max(ih, 1), 1.0)
            scaled_w = iw * scale
            scaled_h = ih * scale

            # Center on page
            x0 = (page_w - scaled_w) / 2
            y0 = (page_h - scaled_h) / 2
            rect = fitz.Rect(x0, y0, x0 + scaled_w, y0 + scaled_h)

            page.insert_image(rect, stream=img_bytes)
            logger.info("  Page %d: inserted image (%d bytes)", i + 1, len(img_bytes))

        pdf_bytes = doc.tobytes()
        doc.close()

        logger.info("  Created %d-page PDF (%d bytes)", len(image_list), len(pdf_bytes))
        return pdf_bytes
