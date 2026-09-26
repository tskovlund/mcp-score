"""Fixtures shared by the unit tests.

Tools that talk to an application take the server's context, which carries
the bridge registry. Every test gets its own registry and a context that
points at it, so tests never see each other's connections.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from mcp_score.bridge import BridgeRegistry
from tests.fakes import FakeBridge, score_context

if TYPE_CHECKING:
    from mcp_score.context import ScoreContext


@pytest.fixture
def registry() -> BridgeRegistry:
    """A registry with fresh, disconnected bridges and nothing active."""
    return BridgeRegistry()


@pytest.fixture
def context(registry: BridgeRegistry) -> ScoreContext:
    """The context a tool receives when the server holds *registry*."""
    return score_context(registry)


@pytest.fixture
def connected_bridge(registry: BridgeRegistry) -> FakeBridge:
    """A connected ``FakeBridge`` installed as the registry's active bridge."""
    bridge = FakeBridge()
    registry.active = bridge
    return bridge
