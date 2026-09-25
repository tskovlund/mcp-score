"""Shared setup for the integration tests.

Integration tests need a real MuseScore Studio install and are skipped
unless ``MCP_SCORE_INTEGRATION=1`` is set, so the plain ``pytest`` run
stays offline and fast.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

INTEGRATION_ENV_VAR = "MCP_SCORE_INTEGRATION"
INTEGRATION_ENABLED_VALUE = "1"
INTEGRATION_MARKER = "integration"
FIXTURES_DIR = Path(__file__).parent / "fixtures"


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Skip ``integration``-marked tests unless explicitly enabled."""
    if os.environ.get(INTEGRATION_ENV_VAR) == INTEGRATION_ENABLED_VALUE:
        return
    skip_marker = pytest.mark.skip(
        reason=f"set {INTEGRATION_ENV_VAR}={INTEGRATION_ENABLED_VALUE} "
        "to run integration tests"
    )
    for item in items:
        if item.get_closest_marker(INTEGRATION_MARKER) is not None:
            item.add_marker(skip_marker)


@pytest.fixture
def fixture_score() -> Path:
    """The committed one-part, one-measure MusicXML score titled "Fixture"."""
    return FIXTURES_DIR / "fixture.musicxml"
