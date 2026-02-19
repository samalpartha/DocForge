"""
DocForge — Template registry.

Ships 3 templates out of the box. Each declares its compatible engines,
required variables, and default layout options.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class TemplateEntry(BaseModel):
    id: str
    name: str
    description: str
    engines: list[str] = Field(default_factory=lambda: ["docgen", "latex"])
    variables: list[str] = Field(default_factory=list)
    default_watermark: str = "INTERNAL"
    include_toc: bool = False


TEMPLATES: dict[str, TemplateEntry] = {
    "product-release": TemplateEntry(
        id="product-release",
        name="Product Release",
        description="Standard product release notes with features, fixes, and breaking changes.",
        engines=["docgen", "latex"],
        variables=[
            "product_name", "version", "release_date", "summary",
            "features", "fixes", "breaking_changes", "links",
        ],
        default_watermark="INTERNAL",
    ),
    "security-advisory": TemplateEntry(
        id="security-advisory",
        name="Security Advisory",
        description="Security-focused release with CVE references and severity indicators.",
        engines=["docgen", "latex"],
        variables=[
            "product_name", "version", "release_date", "summary",
            "fixes", "breaking_changes", "links",
        ],
        default_watermark="CONFIDENTIAL",
    ),
    "api-release": TemplateEntry(
        id="api-release",
        name="API Release",
        description="API changelog with endpoint changes, deprecations, and migration guides.",
        engines=["docgen", "latex"],
        variables=[
            "product_name", "version", "release_date", "summary",
            "features", "breaking_changes", "links",
        ],
        default_watermark="DRAFT",
        include_toc=True,
    ),
}


def get_template(template_id: str) -> TemplateEntry | None:
    return TEMPLATES.get(template_id)


def list_templates() -> list[TemplateEntry]:
    return list(TEMPLATES.values())
