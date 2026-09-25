"""Tests for the bridge registry: which application is active."""

from __future__ import annotations

import pytest

from mcp_score.bridge import BridgeRegistry
from tests.fakes import BridgeCall, FakeBridge


class TestBridgeRegistryActivate:
    @pytest.mark.anyio()
    async def test_activate_connects_bridge_and_makes_it_active(self) -> None:
        # Arrange
        registry = BridgeRegistry()
        bridge = FakeBridge(is_connected=False)

        # Act
        activated = await registry.activate(bridge)

        # Assert
        assert activated is True
        assert registry.active is bridge
        assert bridge.calls == [BridgeCall("connect", ())]

    @pytest.mark.anyio()
    async def test_activate_disconnects_previously_active_bridge(self) -> None:
        # Arrange
        registry = BridgeRegistry()
        previous = FakeBridge("Previous")
        replacement = FakeBridge("Replacement", is_connected=False)
        await registry.activate(previous)

        # Act
        await registry.activate(replacement)

        # Assert
        assert registry.active is replacement
        assert previous.calls[-1] == BridgeCall("disconnect", ())
        assert previous.is_connected is False

    @pytest.mark.anyio()
    async def test_activate_same_bridge_again_does_not_disconnect_it(self) -> None:
        # Arrange
        registry = BridgeRegistry()
        bridge = FakeBridge()
        await registry.activate(bridge)

        # Act
        await registry.activate(bridge)

        # Assert
        assert registry.active is bridge
        assert bridge.calls_to("disconnect") == []

    @pytest.mark.anyio()
    async def test_activate_failure_leaves_nothing_active(self) -> None:
        # Arrange
        registry = BridgeRegistry()
        previous = FakeBridge("Previous")
        unreachable = FakeBridge("Unreachable", is_connected=False)
        unreachable.connect_succeeds = False
        await registry.activate(previous)

        # Act
        activated = await registry.activate(unreachable)

        # Assert
        assert activated is False
        assert registry.active is None
        assert registry.connected() is None
        assert previous.is_connected is False


class TestBridgeRegistryDeactivate:
    @pytest.mark.anyio()
    async def test_deactivate_active_bridge_disconnects_and_clears_it(self) -> None:
        # Arrange
        registry = BridgeRegistry()
        bridge = FakeBridge()
        await registry.activate(bridge)

        # Act
        await registry.deactivate(bridge)

        # Assert
        assert registry.active is None
        assert bridge.calls[-1] == BridgeCall("disconnect", ())

    @pytest.mark.anyio()
    async def test_deactivate_other_bridge_leaves_active_untouched(self) -> None:
        # Arrange
        registry = BridgeRegistry()
        active = FakeBridge("Active")
        other = FakeBridge("Other")
        await registry.activate(active)

        # Act
        await registry.deactivate(other)

        # Assert
        assert registry.active is active
        assert active.is_connected is True
        assert other.calls == [BridgeCall("disconnect", ())]


class TestBridgeRegistryConnected:
    def test_connected_with_nothing_active_returns_none(self) -> None:
        # Arrange
        registry = BridgeRegistry()

        # Act / Assert
        assert registry.connected() is None

    def test_connected_honours_bridge_connection_state(self) -> None:
        # Arrange
        registry = BridgeRegistry()
        bridge = FakeBridge()
        registry.active = bridge

        # Act / Assert
        assert registry.connected() is bridge
        bridge.is_connected = False
        assert registry.connected() is None
