"""
DocForge CLI — Input validation for release JSON payloads.
"""

from typing import Any


REQUIRED_FIELDS = ["product_name", "version"]

OPTIONAL_LIST_FIELDS = ["features", "fixes", "breaking_changes", "links"]


class ValidationError(Exception):
    """Raised when input JSON is missing required fields."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__(f"Validation failed: {'; '.join(errors)}")


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
