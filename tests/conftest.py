"""Shared test configuration and fixtures for DocForge test suite."""

import sys
import os
from pathlib import Path

import pytest

# Add backend to Python path so imports work
backend_dir = str(Path(__file__).parent.parent / "backend")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)


@pytest.fixture(scope="session")
def project_root():
    return Path(__file__).parent.parent


@pytest.fixture(scope="session")
def examples_dir(project_root):
    return project_root / "examples"


@pytest.fixture(scope="session")
def schemas_dir(project_root):
    return project_root / "schemas"


@pytest.fixture(scope="session")
def corpus_dir(project_root):
    return project_root / "tests" / "corpus"
