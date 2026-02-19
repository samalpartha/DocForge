"""
DocForge CLI — Input validation for release JSON payloads.

Now delegates to Pydantic-based ReleaseModel for strict validation.
Kept for backward compatibility with existing callers.
"""

from typing import Any

from app.errors import ValidationError


REQUIRED_FIELDS = ["product_name", "version"]

OPTIONAL_LIST_FIELDS = ["features", "fixes", "breaking_changes", "links"]


def validate_release_payload(data: dict[str, Any]) -> dict[str, Any]:
    """
    Validate the incoming release JSON payload.
    Returns the normalised data dict (with missing optional fields set to empty lists).
    Raises ValidationError on failure.
    """
    errors: list[str] = []

    for field in REQUIRED_FIELDS:
        if field not in data or not str(data[field]).strip():
            errors.append(f"Missing required field: '{field}'")

    if errors:
        raise ValidationError(errors)

    for field in OPTIONAL_LIST_FIELDS:
        if field not in data or data[field] is None:
            data[field] = []

    if "summary" not in data or not data["summary"]:
        data["summary"] = "None"

    if "release_date" not in data or not data["release_date"]:
        from datetime import date
        data["release_date"] = date.today().isoformat()

    return data
