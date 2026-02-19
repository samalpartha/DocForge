"""
DocForge — Asset resolution step.

Resolves image and attachment paths, validates security constraints,
and computes content hashes. Fails fast with clear error messages.

Security controls:
  - Path traversal: blocked (.. not allowed, resolve + prefix check)
  - Type allowlist: jpg, jpeg, png, gif, pdf, txt
  - Max single file: 10 MB
  - Max total assets: 50 MB
  - Max count: 20 files
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from app.errors import (
    AssetNotFoundError,
    AssetPathTraversalError,
    AssetTooLargeError,
    AssetTypeBlockedError,
)
from app.models.release import ReleaseModel
from app.utils.logging import logger, step_timer

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".pdf", ".txt"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
MAX_TOTAL_SIZE = 50 * 1024 * 1024  # 50 MB
MAX_ASSET_COUNT = 20


def _validate_path(rel_path: str, base_dir: Path) -> Path:
    """Resolve a relative path against base_dir with security checks."""
    if ".." in rel_path:
        raise AssetPathTraversalError(rel_path)

    resolved = (base_dir / rel_path).resolve()

    if not str(resolved).startswith(str(base_dir.resolve())):
        raise AssetPathTraversalError(rel_path)

    if not resolved.exists():
        raise AssetNotFoundError(rel_path)

    ext = resolved.suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise AssetTypeBlockedError(rel_path, ext)

    size = resolved.stat().st_size
    if size > MAX_FILE_SIZE:
        raise AssetTooLargeError(rel_path, size / (1024 * 1024), MAX_FILE_SIZE / (1024 * 1024))

    return resolved


def resolve_assets(model: ReleaseModel, asset_dir: Path | None) -> list[str]:
    """
    Resolve all image and attachment paths in the model.

    Sets resolved_path and sha256 on each image/attachment.
    Returns list of warning messages (empty if all clean).
    Raises DocForgeError subclass on security violations.
    """
    if not model.images and not model.attachments:
        return []

    if asset_dir is None:
        return ["No asset directory provided; image/attachment paths will not be resolved."]

    with step_timer("Resolve assets"):
        base = Path(asset_dir).resolve()
        if not base.is_dir():
            return [f"Asset directory does not exist: {asset_dir}"]

        all_assets = list(model.images) + list(model.attachments)
        if len(all_assets) > MAX_ASSET_COUNT:
            raise AssetTooLargeError(
                f"{len(all_assets)} files",
                0,
                MAX_ASSET_COUNT,
            )

        total_size = 0
        warnings: list[str] = []

        for asset in model.images:
            resolved = _validate_path(asset.path, base)
            asset.resolved_path = str(resolved)
            content = resolved.read_bytes()
            asset.sha256 = hashlib.sha256(content).hexdigest()
            total_size += len(content)
            logger.info("  Resolved image: %s (%d bytes, %s)", asset.path, len(content), asset.sha256[:12])

        for asset in model.attachments:
            resolved = _validate_path(asset.path, base)
            asset.resolved_path = str(resolved)
            content = resolved.read_bytes()
            asset.sha256 = hashlib.sha256(content).hexdigest()
            total_size += len(content)
            logger.info("  Resolved attachment: %s (%d bytes)", asset.path, len(content))

        if total_size > MAX_TOTAL_SIZE:
            raise AssetTooLargeError(
                "total assets",
                total_size / (1024 * 1024),
                MAX_TOTAL_SIZE / (1024 * 1024),
            )

        logger.info(
            "  Resolved %d assets (%.1f MB total)",
            len(all_assets), total_size / (1024 * 1024),
        )
        return warnings
