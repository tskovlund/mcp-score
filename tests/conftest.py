"""Fixtures shared by the unit tests.

The tools operate on the module-level bridge ``registry``. Every test gets
that registry in a known state (fresh bridges, nothing active) and leaves
it as it found it, so tests never see each other's connections.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from mcp_score.bridge import BridgeRegistry, DoricoBridge, MuseScoreBridge, registry
from tests.fakes import FakeBridge

if TYPE_CHECKING:
    from collections.abc import Iterator


@pytest.fixture(autouse=True)
def isolated_registry() -> Iterator[BridgeRegistry]:
    """The real registry with fresh, disconnected bridges and nothing active."""
    previous_musescore = registry.musescore
    previous_dorico = registry.dorico
    previous_active = registry.active
    registry.musescore = MuseScoreBridge()
    registry.dorico = DoricoBridge()
    registry.active = None
    yield registry
    registry.musescore = previous_musescore
    registry.dorico = previous_dorico
    registry.active = previous_active


@pytest.fixture
def connected_bridge(isolated_registry: BridgeRegistry) -> FakeBridge:
    """A connected ``FakeBridge`` installed as the registry's active bridge."""
    bridge = FakeBridge()
    isolated_registry.active = bridge
    return bridge
