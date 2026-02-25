"""Tests for the bridge registry — multi-bridge management."""

from __future__ import annotations

from unittest.mock import AsyncMock

from mcp_score.bridge import (
    get_active_bridge,
    get_dorico_bridge,
    get_musescore_bridge,
    get_sibelius_bridge,
    set_active_bridge,
)
from mcp_score.bridge.base import ScoreBridge
from mcp_score.bridge.dorico import DoricoBridge
from mcp_score.bridge.musescore import MuseScoreBridge
from mcp_score.bridge.sibelius import SibeliusBridge


class TestBridgeRegistry:
    def test_no_active_bridge_initially(self) -> None:
        # Arrange — reset global state
        set_active_bridge(None)

        # Act / Assert
        assert get_active_bridge() is None

    def test_set_and_get_active_bridge(self) -> None:
        # Arrange
        mock_bridge = AsyncMock(spec=ScoreBridge)
        set_active_bridge(mock_bridge)

        # Act
        result = get_active_bridge()

        # Assert
        assert result is mock_bridge

        # Cleanup
        set_active_bridge(None)

    def test_clear_active_bridge(self) -> None:
        # Arrange
        mock_bridge = AsyncMock(spec=ScoreBridge)
        set_active_bridge(mock_bridge)

        # Act
        set_active_bridge(None)

        # Assert
        assert get_active_bridge() is None

    def test_get_musescore_bridge_returns_singleton(self) -> None:
        # Act
        bridge1 = get_musescore_bridge()
        bridge2 = get_musescore_bridge()

        # Assert
        assert bridge1 is bridge2
        assert isinstance(bridge1, MuseScoreBridge)

    def test_get_dorico_bridge_returns_singleton(self) -> None:
        # Act
        bridge1 = get_dorico_bridge()
        bridge2 = get_dorico_bridge()

        # Assert
        assert bridge1 is bridge2
        assert isinstance(bridge1, DoricoBridge)

    def test_get_sibelius_bridge_returns_singleton(self) -> None:
        # Act
        bridge1 = get_sibelius_bridge()
        bridge2 = get_sibelius_bridge()

        # Assert
        assert bridge1 is bridge2
        assert isinstance(bridge1, SibeliusBridge)
