import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

FIXTURES = os.path.join(ROOT, "tests", "fixtures")


@pytest.fixture
def fixture_path():
    def build(*parts):
        return os.path.join(FIXTURES, *parts)
    return build


@pytest.fixture
def fixture_text(fixture_path):
    def read(*parts):
        with open(fixture_path(*parts), encoding="utf-8") as handle:
            return handle.read()
    return read
