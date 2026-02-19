"""
DocForge CLI — Foxit PDF Services API client.

Async workflow: upload → operation → poll task → download result.

Base URL pattern: https://na1.fusion.foxit.com/pdf-services
Auth: client_id / client_secret headers on every request.

Key endpoints used:
  POST /api/documents/upload           — upload a PDF (multipart)
  POST /api/documents/enhance/pdf-watermark  — add watermark
  POST /api/documents/security/pdf-protect   — password-protect
  POST /api/documents/modify/pdf-flatten     — flatten annotations
  GET  /api/tasks/{taskId}             — poll task status
  GET  /api/documents/{docId}/download — download result
"""

import asyncio
from typing import Any

import httpx

from app.foxit.auth import FoxitCredentials
from app.utils.logging import logger, step_timer

MAX_RETRIES = 1


class PDFServicesClient:
    """Thin async wrapper around the Foxit PDF Services REST API."""

    def __init__(
        self,
        base_url: str,
        credentials: FoxitCredentials,
        poll_interval: float = 2.0,
        poll_timeout: float = 120.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.credentials = credentials
        self.poll_interval = poll_interval
        self.poll_timeout = poll_timeout

    def _headers(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        h = self.credentials.as_headers()
        if extra:
            h.update(extra)
        return h

    async def upload_pdf(self, pdf_bytes: bytes, filename: str = "document.pdf") -> str:
        """Upload a PDF and return its documentId."""
        with step_timer("PDF Services — upload document"):
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    f"{self.base_url}/api/documents/upload",
                    headers=self._headers(),
                    files={"file": (filename, pdf_bytes, "application/pdf")},
                )
                resp.raise_for_status()
                data = resp.json()
                doc_id = data.get("documentId") or data.get("data", {}).get("documentId")
                logger.info("  Uploaded %d bytes → docId %s", len(pdf_bytes), doc_id)
                return doc_id

    async def _submit_operation(self, endpoint: str, payload: dict[str, Any]) -> dict:
        """POST an operation and return the JSON response (contains taskId).
        Retries once on transient failure."""
        last_err = None
        for attempt in range(1, MAX_RETRIES + 2):
            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    resp = await client.post(
                        f"{self.base_url}{endpoint}",
                        headers=self._headers({"Content-Type": "application/json"}),
                        json=payload,
                    )
                    if not resp.is_success:
                        logger.error(
                            "  PDF Services %s returned %d (attempt %d/%d): %s",
                            endpoint, resp.status_code, attempt, MAX_RETRIES + 1, resp.text,
                        )
                    resp.raise_for_status()
                    return resp.json()
            except (httpx.HTTPStatusError, httpx.TransportError) as exc:
                last_err = exc
                if attempt <= MAX_RETRIES:
                    logger.warning("  Retrying %s in 2s (attempt %d failed)", endpoint, attempt)
                    await asyncio.sleep(2)
        raise last_err  # type: ignore[misc]

    async def _poll_task(self, task_id: str) -> str:
        """Poll until the task completes and return the result documentId."""
        elapsed = 0.0
        async with httpx.AsyncClient(timeout=30.0) as client:
            while elapsed < self.poll_timeout:
                resp = await client.get(
                    f"{self.base_url}/api/tasks/{task_id}",
                    headers=self._headers(),
                )
                resp.raise_for_status()
                task = resp.json()

                status = (
                    task.get("status")
                    or task.get("data", {}).get("status")
                    or ""
                ).upper()

                if status in ("COMPLETED", "DONE", "SUCCESS"):
                    result_id = (
                        task.get("resultDocumentId")
                        or task.get("data", {}).get("resultDocumentId")
                        or task.get("documentId")
                        or task.get("data", {}).get("documentId")
                    )
                    return result_id

                if status in ("FAILED", "ERROR"):
                    msg = (
                        task.get("message")
                        or task.get("data", {}).get("message")
                        or task.get("error")
                        or task.get("data", {}).get("error")
                        or "unknown"
                    )
                    logger.error("  Task %s failed: %s", task_id, msg)
                    raise RuntimeError(f"Task {task_id} failed: {msg}")

                await asyncio.sleep(self.poll_interval)
                elapsed += self.poll_interval

        raise TimeoutError(f"Task {task_id} did not complete within {self.poll_timeout}s")

    async def _run_operation(self, name: str, endpoint: str, payload: dict[str, Any]) -> str:
        """Submit an operation, poll until done, return result documentId."""
        with step_timer(f"PDF Services — {name}"):
            result = await self._submit_operation(endpoint, payload)
            task_id = (
                result.get("taskId")
                or result.get("data", {}).get("taskId")
            )
            if not task_id:
                return (
                    result.get("resultDocumentId")
                    or result.get("data", {}).get("resultDocumentId")
                    or result.get("documentId")
                    or result.get("data", {}).get("documentId")
                )
            return await self._poll_task(task_id)

    async def download_pdf(self, document_id: str) -> bytes:
        """Download a document by ID and return raw bytes."""
        with step_timer("PDF Services — download result"):
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.get(
                    f"{self.base_url}/api/documents/{document_id}/download",
                    headers=self._headers(),
                )
                resp.raise_for_status()
                logger.info("  Downloaded %d bytes", len(resp.content))
                return resp.content

    # ---- High-level operations ----

    async def add_watermark(
        self,
        document_id: str,
        text: str = "INTERNAL",
        opacity: int = 15,
        rotation: int = -45,
        font_size: int = 48,
        color: str = "#AAAAAA",
    ) -> str:
        """Add a text watermark. Returns new documentId.
        opacity: integer 0-100 (not a float)."""
        return await self._run_operation(
            "add watermark",
            "/api/documents/enhance/pdf-watermark",
            {
                "documentId": document_id,
                "config": {
                    "text": text,
                    "type": "TEXT",
                    "position": "CENTER",
                    "opacity": int(opacity),
                    "rotation": int(rotation),
                    "fontSize": int(font_size),
                    "color": color,
                },
            },
        )

    async def protect_pdf(
        self,
        document_id: str,
        user_password: str | None = None,
        owner_password: str | None = None,
    ) -> str:
        """Password-protect a PDF. Returns new documentId."""
        config: dict[str, Any] = {}
        if user_password:
            config["userPassword"] = user_password
        if owner_password:
            config["ownerPassword"] = owner_password
        if not config:
            config["ownerPassword"] = "docforge-owner"

        return await self._run_operation(
            "protect PDF",
            "/api/documents/security/pdf-protect",
            {"documentId": document_id, "config": config},
        )

    async def flatten_pdf(self, document_id: str) -> str:
        """Flatten annotations/forms. Returns new documentId."""
        return await self._run_operation(
            "flatten PDF",
            "/api/documents/modify/pdf-flatten",
            {"documentId": document_id},
        )
