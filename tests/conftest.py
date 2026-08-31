"""Shared fixtures for the tflows test suite."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.fakes import make_bot  # noqa: E402


@pytest.fixture
def bot():
    return make_bot()
