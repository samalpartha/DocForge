"""Integration tests for the pipeline orchestrator with mock Foxit APIs."""

import pytest
from unittest.mock import patch, AsyncMock

from app.models.job import JobState


class TestJobOrchestrator:
    """Test the orchestrator flow with mocked external API calls."""

    @pytest.mark.asyncio
    async def test_orchestrator_init(self):
        from app.foxit.pipeline import JobOrchestrator
        orch = JobOrchestrator(
            release_data={"product_name": "Test", "version": "1.0"},
            engine="docgen",
        )
        assert orch.state == JobState.RECEIVED
        assert orch.engine == "docgen"
        assert len(orch.job_id) == 12

    @pytest.mark.asyncio
    async def test_orchestrator_validates_input(self):
        from app.foxit.pipeline import JobOrchestrator
        orch = JobOrchestrator(
            release_data={"product_name": "Test", "version": "1.0"},
            engine="docgen",
        )
        # Just test the validation step
        await orch._step_validate()
        assert orch.state == JobState.VALIDATED
        assert orch.ctx.release is not None
        assert orch.ctx.release.product_name == "Test"

    @pytest.mark.asyncio
    async def test_orchestrator_rejects_invalid_input(self):
        from app.foxit.pipeline import JobOrchestrator
        orch = JobOrchestrator(
            release_data={"version": "1.0"},  # missing product_name
            engine="docgen",
        )
        with pytest.raises(Exception):
            await orch._step_validate()


class TestTemplateRegistry:
    def test_list_templates(self):
        from app.templates.registry import list_templates
        templates = list_templates()
        assert len(templates) >= 3

    def test_get_template(self):
        from app.templates.registry import get_template
        t = get_template("product-release")
        assert t is not None
        assert t.id == "product-release"

    def test_unknown_template(self):
        from app.templates.registry import get_template
        t = get_template("nonexistent")
        assert t is None
