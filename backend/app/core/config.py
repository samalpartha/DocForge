"""
DocForge CLI — Backend Configuration
Loads .env automatically, then reads all settings from environment variables.
"""

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

_env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(_env_path)


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


def _load_config() -> AppConfig:
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


def _validate_config(cfg: AppConfig) -> None:
    """Fail fast if Foxit credentials are missing."""
    missing: list[str] = []
    if not cfg.docgen.client_id:
        missing.append("FOXIT_DOCGEN_CLIENT_ID")
    if not cfg.docgen.client_secret:
        missing.append("FOXIT_DOCGEN_CLIENT_SECRET")
    if not cfg.pdf_services.client_id:
        missing.append("FOXIT_PDF_SERVICES_CLIENT_ID")
    if not cfg.pdf_services.client_secret:
        missing.append("FOXIT_PDF_SERVICES_CLIENT_SECRET")
    if missing:
        print(
            f"\n  ERROR: Missing Foxit credentials: {', '.join(missing)}\n"
            f"  Copy backend/.env.example → backend/.env and fill in your keys.\n"
            f"  Get free keys at https://app.developer-api.foxit.com/pricing\n",
            file=sys.stderr,
        )
        sys.exit(1)


settings = _load_config()
_validate_config(settings)
