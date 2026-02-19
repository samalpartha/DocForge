"""
DocForge — Typed release data model.

Every engine, pipeline step, and output formatter works against ReleaseModel.
No raw dicts leak across boundaries.
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class FeatureModel(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=2000)


class FixModel(BaseModel):
    id: str = Field(min_length=1, max_length=50)
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)


class BreakingChangeModel(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=2000)
    migration: str = Field(min_length=1, max_length=2000)


class LinkModel(BaseModel):
    label: str = Field(min_length=1, max_length=200)
    url: str = Field(max_length=2000)


class ImageModel(BaseModel):
    path: str = Field(min_length=1, max_length=500)
    caption: str = Field(default="", max_length=500)
    width_percent: int = Field(default=80, ge=10, le=100)
    placement: Literal["inline", "full_width"] = "inline"
    resolved_path: str | None = Field(default=None, exclude=True)
    sha256: str | None = Field(default=None, exclude=True)


class AttachmentModel(BaseModel):
    label: str = Field(min_length=1, max_length=200)
    path: str = Field(min_length=1, max_length=500)
    type: Literal["appendix", "embed"] = "appendix"
    resolved_path: str | None = Field(default=None, exclude=True)
    sha256: str | None = Field(default=None, exclude=True)


class ReleaseModel(BaseModel):
    """
    Canonical release data model.

    All pipeline steps receive this typed structure instead of raw dicts.
    Input JSON is validated and normalised into ReleaseModel at the start.
    """

    schema_version: str = "1.0"
    product_name: str = Field(min_length=1, max_length=200)
    version: str = Field(min_length=1, max_length=50)
    release_date: str = Field(default_factory=lambda: date.today().isoformat())
    summary: str = Field(default="", max_length=5000)
    features: list[FeatureModel] = Field(default_factory=list)
    fixes: list[FixModel] = Field(default_factory=list)
    breaking_changes: list[BreakingChangeModel] = Field(default_factory=list)
    links: list[LinkModel] = Field(default_factory=list)
    images: list[ImageModel] = Field(default_factory=list)
    attachments: list[AttachmentModel] = Field(default_factory=list)

    def to_legacy_dict(self) -> dict:
        """Convert back to the dict format expected by existing engines."""
        d = self.model_dump()
        d["product_name"] = d.pop("product_name")
        return d
