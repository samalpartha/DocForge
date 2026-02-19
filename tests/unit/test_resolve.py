"""Unit tests for asset resolution and path traversal blocking."""

import os
import tempfile
import pytest
from pathlib import Path

from app.models.release import ReleaseModel, ImageModel, AttachmentModel
from app.pipeline.resolve_assets import resolve_assets, _validate_path
from app.errors import (
    AssetNotFoundError,
    AssetPathTraversalError,
    AssetTypeBlockedError,
    AssetTooLargeError,
)


@pytest.fixture
def asset_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        (Path(tmpdir) / "screenshot.png").write_bytes(b"\x89PNG" + b"\0" * 100)
        (Path(tmpdir) / "doc.pdf").write_bytes(b"%PDF" + b"\0" * 100)
        (Path(tmpdir) / "notes.txt").write_bytes(b"hello world")
        yield tmpdir


class TestValidatePath:
    def test_valid_file(self, asset_dir):
        result = _validate_path("screenshot.png", Path(asset_dir))
        assert result.exists()

    def test_path_traversal_dotdot(self, asset_dir):
        with pytest.raises(AssetPathTraversalError):
            _validate_path("../../etc/passwd", Path(asset_dir))

    def test_file_not_found(self, asset_dir):
        with pytest.raises(AssetNotFoundError):
            _validate_path("nonexistent.png", Path(asset_dir))

    def test_type_blocked(self, asset_dir):
        (Path(asset_dir) / "script.exe").write_bytes(b"\0")
        with pytest.raises(AssetTypeBlockedError):
            _validate_path("script.exe", Path(asset_dir))


class TestResolveAssets:
    def test_no_assets_returns_empty(self):
        m = ReleaseModel(product_name="Test", version="1.0")
        warnings = resolve_assets(m, None)
        assert warnings == []

    def test_images_resolved(self, asset_dir):
        m = ReleaseModel(
            product_name="Test", version="1.0",
            images=[ImageModel(path="screenshot.png")],
        )
        warnings = resolve_assets(m, asset_dir)
        assert m.images[0].resolved_path is not None
        assert m.images[0].sha256 is not None
        assert len(m.images[0].sha256) == 64

    def test_missing_asset_dir(self):
        m = ReleaseModel(
            product_name="Test", version="1.0",
            images=[ImageModel(path="screenshot.png")],
        )
        warnings = resolve_assets(m, "/nonexistent/dir")
        assert any("does not exist" in w for w in warnings)

    def test_attachments_resolved(self, asset_dir):
        m = ReleaseModel(
            product_name="Test", version="1.0",
            attachments=[AttachmentModel(label="Notes", path="notes.txt")],
        )
        warnings = resolve_assets(m, asset_dir)
        assert m.attachments[0].resolved_path is not None
        assert m.attachments[0].sha256 is not None
