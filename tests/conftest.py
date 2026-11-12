from pathlib import Path

import pytest

from cybersprite.core.canonical import load_project
from cybersprite.core.projects import new_project

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def project():
    return new_project(width=4, height=3, frames=2, name="Test")


@pytest.fixture
def appendix():
    return load_project(ROOT / "tests/fixtures/appendix_a/project.json")
