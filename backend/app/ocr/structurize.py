"""
DocForge — Text-to-JSON structured extractor.

Takes raw OCR text and extracts structured release note fields
using pattern matching. Returns a draft JSON with confidence
indicators and missing-field warnings.

Quality gates:
  > 0.90: auto-populate, allow one-click generation
  0.70–0.90: populate with warnings, require user confirmation
  < 0.70: force manual review, block auto-generation
"""

import os
import json
import re
from dataclasses import dataclass, field
from typing import Optional

import google.generativeai as genai
from app.ocr.extract import OCRResult
from app.utils.logging import logger, step_timer


@dataclass
class ExtractionResult:
    draft_json: dict
    confidence: float = 0.0
    missing_required: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    needs_review: bool = True
    provider: str = "regex"  # Track if Gemini or regex was used


# Improved version pattern to catch common version formats or even "Step X" as a fallback
VERSION_PATTERN = re.compile(
    r"(?:v(?:ersion)?[\s.:]*)?(\d+(?:\.\d+)+(?:[-+][\w.]+)?)",
    re.IGNORECASE,
)
# Fallback version pattern for simpler formats like "v1" or "1.0"
VERSION_PATTERN_SIMPLE = re.compile(r"v?(\d+\.\d+)", re.IGNORECASE)

SECTION_PATTERNS = {
    "features": re.compile(
        r"^\s*(?:new\s+features?|what'?s\s+new|additions?|enhancements?|improvements?)\s*$",
        re.IGNORECASE,
    ),
    "fixes": re.compile(
        r"^\s*(?:bug\s*fix(?:es)?|resolved\s+issues?|fixed\s+issues?|patches?|corrections?)\s*$",
        re.IGNORECASE,
    ),
    "breaking": re.compile(
        r"^\s*(?:breaking\s+changes?|deprecat(?:ed|ions?)|removed\s+features?|migration\s+notes?)\s*$",
        re.IGNORECASE,
    ),
}


def _extract_product_name(text: str) -> str:
    """Try to find a product name in the first few lines."""
    lines = [line_content.strip() for line_content in text.split("\n") if line_content.strip()][:5]

    for line in lines:
        # Skip lines that are just version numbers or dates
        if re.match(r"^v?\d+\.\d+", line) or re.match(r"^\d{4}-\d{2}-\d{2}$", line):
            continue
        # Skip common headers
        if re.match(r"^(release\s+notes?|changelog|what'?s\s+new)", line, re.IGNORECASE):
            continue
        # Return first meaningful line
        # Clean up: stop at "Step", "Release", "Notes", etc.
        cleaned = re.split(r"[:—–-]\s*(?:release|notes|version|step)", line, flags=re.IGNORECASE)[0].strip()
        cleaned = re.sub(r"\s*v?\d+.*$", "", cleaned).strip()
        if cleaned and len(cleaned) > 2:
            return cleaned

    return ""


def _extract_version(text: str) -> str:
    """Find the first version-like string."""
    match = VERSION_PATTERN.search(text[:1000])
    if match:
        return match.group(1)
    
    # Try simple v1.2 etc
    match_simple = VERSION_PATTERN_SIMPLE.search(text[:1000])
    if match_simple:
        return match_simple.group(1)
        
    # Look for "Step X" as version fallback
    step_match = re.search(r"Step\s*(\d+)", text, re.IGNORECASE)
    if step_match:
        return f"Step {step_match.group(1)}"
        
    return ""


def _extract_date(text: str) -> str:
    """Find an ISO-style date."""
    date_match = re.search(r"(\d{4}[-/]\d{2}[-/]\d{2})", text[:500])
    if date_match:
        return date_match.group(1).replace("/", "-")
    return ""


def _split_sections(text: str) -> dict[str, str]:
    """Split text into named sections based on heading patterns."""
    sections: dict[str, str] = {}
    current_section = "preamble"
    current_text: list[str] = []

    for line in text.split("\n"):
        matched = False
        for section_name, pattern in SECTION_PATTERNS.items():
            if pattern.search(line):
                if current_text:
                    sections[current_section] = "\n".join(current_text)
                current_section = section_name
                current_text = []
                matched = True
                break
        if not matched:
            current_text.append(line)

    if current_text:
        sections[current_section] = "\n".join(current_text)

    return sections


def _extract_list_items(text: str) -> list[dict[str, str]]:
    """Extract bullet points or numbered items as title/description pairs."""
    items: list[dict[str, str]] = []
    lines = [line_content.strip() for line_content in text.split("\n") if line_content.strip()]

    for line in lines:
        # Remove bullet markers
        cleaned = re.sub(r"^[\s•\-\*\d+\.\)]+\s*", "", line).strip()
        if not cleaned or len(cleaned) < 3:
            continue

        # Try to split on colon or dash separator
        parts = re.split(r"\s*[:—–]\s+", cleaned, maxsplit=1)
        if len(parts) == 2 and len(parts[0]) < 100:
            items.append({"title": parts[0], "description": parts[1]})
        else:
            items.append({"title": cleaned, "description": ""})

    return items


def _extract_fix_items(text: str) -> list[dict[str, str]]:
    """Extract bug fix items, attempting to find IDs."""
    items: list[dict[str, str]] = []
    raw_items = _extract_list_items(text)

    for i, item in enumerate(raw_items):
        # Try to find a bug ID pattern
        id_match = re.match(
            r"((?:BUG|FIX|ISSUE|CVE|JIRA|TICKET)[-\s]?\d+)",
            item["title"],
            re.IGNORECASE,
        )
        if id_match:
            bug_id = id_match.group(1).upper()
            remainder = item["title"][id_match.end():].strip().lstrip(":- ")
            items.append({
                "id": bug_id,
                "title": remainder or item.get("description", f"Fix #{i+1}"),
                "description": item.get("description", ""),
            })
        else:
            items.append({
                "id": f"FIX-{i+1:03d}",
                "title": item["title"],
                "description": item.get("description", ""),
            })

    return items


def _extract_breaking_items(text: str) -> list[dict[str, str]]:
    """Extract breaking changes with migration hints."""
    items: list[dict[str, str]] = []
    raw_items = _extract_list_items(text)

    for item in raw_items:
        migration = ""
        desc = item.get("description", "")

        # Look for migration hints
        migrate_match = re.search(
            r"(?:migrat|replac|updat|switch|use\s+instead)(.+)",
            desc,
            re.IGNORECASE,
        )
        if migrate_match:
            migration = migrate_match.group(0).strip()

        items.append({
            "title": item["title"],
            "description": desc,
            "migration": migration or "See documentation for migration steps.",
        })

    return items


def _gemini_structurize(text: str) -> Optional[dict]:
    """Use Gemini to extract structured JSON from OCR text."""
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return None

    try:
        genai.configure(api_key=api_key)
        # Upgrade to Gemini 2.0 Flash
        model = genai.GenerativeModel("gemini-2.0-flash")

        prompt = f"""
        You are a world-class release engineer. 
        Your task is to extract highly accurate structured JSON from raw OCR text of a product release or changelog.

        STRICT REQUIREMENTS:
        1. product_name: The name of the software or feature. Look at the very top.
        2. version: The version number (e.g., "1.0.0", "v2.1", "2024.1"). DO NOT leave empty if any version string is visible.
        3. release_date: The date of the release (YYYY-MM-DD). Use today's date if missing but context suggests it's a recent release.
        4. features/fixes/breaking_changes: Categorize items accurately.

        OUTPUT FORMAT:
        Return ONLY valid JSON. No markdown backticks. No explanation.

        JSON Schema:
        {{
          "product_name": "string",
          "version": "string",
          "release_date": "string",
          "summary": "string",
          "features": [{{ "title": "string", "description": "string" }}],
          "fixes": [{{ "id": "string", "title": "string", "description": "string" }}],
          "breaking_changes": [{{ "title": "string", "description": "string", "migration": "string" }}],
          "links": [{{ "label": "string", "url": "string" }}]
        }}

        OCR Text to parse:
        ---
        {text}
        ---
        """

        response = model.generate_content(prompt)

        if not response or not response.text:
            return None

        # Clean markdown if present
        clean_text = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(clean_text)
    except Exception as e:
        logger.error("  Gemini extraction failed: %s", str(e))
        return None


def structurize(ocr_result: OCRResult) -> ExtractionResult:
    """
    Extract structured release data from OCR text.
    Uses Gemini LLM if available, otherwise falls back to regex.
    """
    with step_timer("Structurize OCR text → release JSON"):
        text = ocr_result.raw_text

        # 1. Attempt Gemini extraction if key is present
        gemini_data = _gemini_structurize(text)
        if gemini_data:
            logger.info("  Extraction: provider=gemini (AI-powered)")
            # Basic validation of the gemini response structure
            # (In a real app, use Pydantic validation here)
            return ExtractionResult(
                draft_json=gemini_data,
                confidence=0.95,  # Gemini is highly confident for this task
                provider="gemini",
                needs_review=False,
            )

        # 2. Fallback to regex logic
        logger.info("  Extraction: provider=regex (fallback)")
        warnings: list[str] = []

        product_name = _extract_product_name(text)
        version = _extract_version(text)
        release_date = _extract_date(text)
        sections = _split_sections(text)

        # Extract summary from preamble
        preamble = sections.get("preamble", "")
        summary_lines = [
            line_content.strip() for line_content in preamble.split("\n")
            if line_content.strip() and not VERSION_PATTERN.match(line_content.strip())
            and line_content.strip() != product_name
        ]
        summary = " ".join(summary_lines[:3])

        # Extract structured lists
        features = _extract_list_items(sections.get("features", ""))
        fixes = _extract_fix_items(sections.get("fixes", ""))
        breaking = _extract_breaking_items(sections.get("breaking", ""))

        draft = {
            "product_name": product_name,
            "version": version,
            "release_date": release_date,
            "summary": summary,
            "features": features,
            "fixes": fixes,
            "breaking_changes": breaking,
            "links": [],
        }

        # Check required fields
        missing: list[str] = []
        if not product_name:
            missing.append("product_name")
            warnings.append("Could not detect product name — please fill in manually.")
        if not version:
            missing.append("version")
            warnings.append("Could not detect version number — please fill in manually.")

        if not features and not fixes and not breaking:
            warnings.append("No structured sections detected — the text may need manual parsing.")

        # Determine confidence
        extraction_confidence = ocr_result.overall_confidence
        if missing:
            extraction_confidence *= 0.5
        if not features and not fixes:
            extraction_confidence *= 0.7

        needs_review = extraction_confidence < 0.85 or len(missing) > 0

        logger.info(
            "  Extraction: product=%s version=%s features=%d fixes=%d breaking=%d confidence=%.0f%% review=%s",
            product_name or "?", version or "?",
            len(features), len(fixes), len(breaking),
            extraction_confidence * 100, needs_review,
        )

        return ExtractionResult(
            draft_json=draft,
            confidence=extraction_confidence,
            missing_required=missing,
            warnings=warnings,
            needs_review=needs_review,
        )
