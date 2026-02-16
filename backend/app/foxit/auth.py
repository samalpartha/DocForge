"""
DocForge CLI — Foxit API authentication helpers.

Both the Document Generation API and the PDF Services API authenticate
via client_id / client_secret headers on every request.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class FoxitCredentials:
    client_id: str
    client_secret: str

    def as_headers(self) -> dict[str, str]:
        """Return the auth headers required by Foxit APIs."""
        return {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }
