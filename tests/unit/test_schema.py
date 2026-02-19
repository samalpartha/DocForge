"""Unit tests for JSON Schema validation edge cases."""

import json
import pytest
import jsonschema

SCHEMA_PATH = "schemas/release.schema.json"


@pytest.fixture
def schema():
    with open(SCHEMA_PATH) as f:
        return json.load(f)


def _validate(schema, data):
    jsonschema.validate(instance=data, schema=schema)


class TestSchemaValidation:
    def test_minimal_valid(self, schema):
        _validate(schema, {"product_name": "Acme", "version": "1.0.0"})

    def test_missing_product_name(self, schema):
        with pytest.raises(jsonschema.ValidationError):
            _validate(schema, {"version": "1.0.0"})

    def test_missing_version(self, schema):
        with pytest.raises(jsonschema.ValidationError):
            _validate(schema, {"product_name": "Acme"})

    def test_empty_product_name(self, schema):
        with pytest.raises(jsonschema.ValidationError):
            _validate(schema, {"product_name": "", "version": "1.0.0"})

    def test_valid_features(self, schema):
        _validate(schema, {
            "product_name": "Acme",
            "version": "1.0.0",
            "features": [{"title": "Feature A", "description": "Desc A"}],
        })

    def test_feature_missing_title(self, schema):
        with pytest.raises(jsonschema.ValidationError):
            _validate(schema, {
                "product_name": "Acme",
                "version": "1.0.0",
                "features": [{"description": "No title"}],
            })

    def test_valid_fix(self, schema):
        _validate(schema, {
            "product_name": "Acme",
            "version": "1.0.0",
            "fixes": [{"id": "BUG-1", "title": "Fix crash"}],
        })

    def test_fix_missing_id(self, schema):
        with pytest.raises(jsonschema.ValidationError):
            _validate(schema, {
                "product_name": "Acme",
                "version": "1.0.0",
                "fixes": [{"title": "No ID"}],
            })

    def test_breaking_change_requires_migration(self, schema):
        with pytest.raises(jsonschema.ValidationError):
            _validate(schema, {
                "product_name": "Acme",
                "version": "1.0.0",
                "breaking_changes": [{"title": "Removed", "description": "Gone"}],
            })

    def test_valid_link(self, schema):
        _validate(schema, {
            "product_name": "Acme",
            "version": "1.0.0",
            "links": [{"label": "Docs", "url": "https://example.com"}],
        })

    def test_valid_image(self, schema):
        _validate(schema, {
            "product_name": "Acme",
            "version": "1.0.0",
            "images": [{"path": "screenshot.png"}],
        })

    def test_empty_sections(self, schema):
        _validate(schema, {
            "product_name": "Acme",
            "version": "1.0.0",
            "features": [],
            "fixes": [],
            "breaking_changes": [],
        })

    def test_version_with_prerelease(self, schema):
        _validate(schema, {
            "product_name": "Acme",
            "version": "2.0.0-beta.1",
        })
