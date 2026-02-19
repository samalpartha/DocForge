"""
DocForge — OCR text extraction module.

Extracts text from images and scanned PDFs using pytesseract.
Returns structured blocks with confidence scores per line.

Falls back to pymupdf text extraction for born-digital PDFs.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PIL import Image

from app.utils.logging import logger, step_timer


@dataclass
class OCRBlock:
    text: str
    confidence: float  # 0.0 to 1.0
    line_num: int = 0
    block_num: int = 0


@dataclass
class OCRResult:
    blocks: list[OCRBlock] = field(default_factory=list)
    raw_text: str = ""
    overall_confidence: float = 0.0
    page_count: int = 1
    method: str = "tesseract"  # tesseract | pymupdf | none


def _preprocess_image(image_bytes: bytes) -> "Image.Image":
    """Convert to grayscale and apply threshold for better OCR accuracy."""
    from PIL import Image, ImageFilter

    img = Image.open(io.BytesIO(image_bytes))

    if img.mode != "L":
        img = img.convert("L")

    img = img.filter(ImageFilter.SHARPEN)

    return img


def extract_from_image(image_bytes: bytes) -> OCRResult:
    """
    Extract text from an image using Tesseract OCR.

    Returns structured blocks with per-line confidence scores.
    """
    with step_timer("OCR — extract text from image"):
        try:
            import pytesseract
        except ImportError:
            logger.warning("pytesseract not installed — OCR unavailable")
            return OCRResult(method="none")

        try:
            import PIL  # noqa: F401
        except ImportError:
            logger.warning("Pillow not installed — OCR unavailable")
            return OCRResult(method="none")

        img = _preprocess_image(image_bytes)

        data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)

        blocks: list[OCRBlock] = []
        current_line = -1
        line_text = ""
        line_confs: list[float] = []

        for i in range(len(data["text"])):
            text = data["text"][i].strip()
            conf = float(data["conf"][i])
            line = data["line_num"][i]
            block = data["block_num"][i]

            if not text or conf < 0:
                continue

            if line != current_line and current_line >= 0:
                if line_text.strip():
                    avg_conf = sum(line_confs) / len(line_confs) / 100.0 if line_confs else 0
                    blocks.append(OCRBlock(
                        text=line_text.strip(),
                        confidence=avg_conf,
                        line_num=current_line,
                        block_num=block,
                    ))
                line_text = ""
                line_confs = []

            current_line = line
            line_text += " " + text
            line_confs.append(conf)

        if line_text.strip() and line_confs:
            avg_conf = sum(line_confs) / len(line_confs) / 100.0
            blocks.append(OCRBlock(
                text=line_text.strip(),
                confidence=avg_conf,
                line_num=current_line,
            ))

        raw_text = "\n".join(b.text for b in blocks)
        overall = sum(b.confidence for b in blocks) / len(blocks) if blocks else 0.0

        logger.info(
            "  OCR: %d lines extracted, overall confidence %.0f%%",
            len(blocks), overall * 100,
        )

        return OCRResult(
            blocks=blocks,
            raw_text=raw_text,
            overall_confidence=overall,
            page_count=1,
            method="tesseract",
        )


def extract_from_pdf(pdf_bytes: bytes) -> OCRResult:
    """
    Extract text from a PDF. Uses pymupdf for born-digital PDFs.
    Falls back to OCR (render page → tesseract) for scanned PDFs.
    """
    with step_timer("OCR — extract text from PDF"):
        try:
            import fitz
        except ImportError:
            logger.warning("pymupdf not installed — PDF text extraction unavailable")
            return OCRResult(method="none")

        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        blocks: list[OCRBlock] = []
        all_text = []

        for page_num, page in enumerate(doc):
            text = page.get_text().strip()

            if text and len(text) > 20:
                for line_num, line in enumerate(text.split("\n")):
                    line = line.strip()
                    if line:
                        blocks.append(OCRBlock(
                            text=line,
                            confidence=0.99,
                            line_num=line_num,
                            block_num=page_num,
                        ))
                all_text.append(text)
            else:
                # Scanned page — render to image and OCR
                pix = page.get_pixmap(dpi=300)
                img_bytes = pix.tobytes("png")
                page_result = extract_from_image(img_bytes)
                blocks.extend(page_result.blocks)
                all_text.append(page_result.raw_text)

        doc.close()

        raw_text = "\n".join(all_text)
        overall = sum(b.confidence for b in blocks) / len(blocks) if blocks else 0.0
        method = "pymupdf" if all(b.confidence > 0.95 for b in blocks) else "tesseract"

        logger.info(
            "  PDF extraction: %d lines, %d pages, confidence %.0f%%, method=%s",
            len(blocks), len(doc) if not doc.is_closed else 0, overall * 100, method,
        )

        return OCRResult(
            blocks=blocks,
            raw_text=raw_text,
            overall_confidence=overall,
            page_count=len(all_text),
            method=method,
        )
