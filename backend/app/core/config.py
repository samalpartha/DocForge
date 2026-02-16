"""
DocForge CLI — Backend Configuration
Loads all settings from environment variables with sensible defaults.
"""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class FoxitDocGenConfig:
    """Foxit Document Generation API credentials."""
    base_url: str
    client_id: str
    client_secret: str


@dataclass(frozen=True)
class FoxitPDFServicesConfig:
    """Foxit PDF Services API credentials."""
    base_url: str
    client_id: str
    client_secret: str


@dataclass(frozen=True)
class AppConfig:
    """Top-level application configuration."""
    host: str
    port: int
    debug: bool
    docgen: FoxitDocGenConfig
    pdf_services: FoxitPDFServicesConfig
    template_dir: str
    poll_interval: float
    poll_timeout: float


def load_config() -> AppConfig:
    return AppConfig(
        host=os.getenv("APP_HOST", "0.0.0.0"),
        port=int(os.getenv("APP_PORT", "8000")),
        debug=os.getenv("APP_DEBUG", "false").lower() == "true",
        docgen=FoxitDocGenConfig(
            base_url=os.getenv(
                "FOXIT_DOCGEN_BASE_URL",
                "https://na1.fusion.foxit.com",
            ),
            client_id=os.getenv("FOXIT_DOCGEN_CLIENT_ID", ""),
            client_secret=os.getenv("FOXIT_DOCGEN_CLIENT_SECRET", ""),
        ),
        pdf_services=FoxitPDFServicesConfig(
            base_url=os.getenv(
                "FOXIT_PDF_SERVICES_BASE_URL",
                "https://na1.fusion.foxit.com/pdf-services",
            ),
            client_id=os.getenv("FOXIT_PDF_SERVICES_CLIENT_ID", ""),
            client_secret=os.getenv("FOXIT_PDF_SERVICES_CLIENT_SECRET", ""),
        ),
        template_dir=os.getenv(
            "TEMPLATE_DIR",
            os.path.join(os.path.dirname(__file__), "..", "..", "..", "templates"),
        ),
        poll_interval=float(os.getenv("FOXIT_POLL_INTERVAL", "2.0")),
        poll_timeout=float(os.getenv("FOXIT_POLL_TIMEOUT", "120.0")),
    )


settings = load_config()
