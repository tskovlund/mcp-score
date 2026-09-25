"""Tests for DoricoBridge: only the defaults it adds to RemoteControlBridge.

The protocol itself is tested in ``test_remote_control_bridge.py``.
"""

from __future__ import annotations

from mcp_score.bridge.dorico import DEFAULT_PORT, DoricoBridge
from mcp_score.bridge.remote_control import DEFAULT_CLIENT_NAME


class TestDoricoBridgeDefaults:
    def test_default_bridge_targets_dorico_remote_control_port(self) -> None:
        # Arrange / Act
        bridge = DoricoBridge()

        # Assert
        assert bridge.application_name == "Dorico"
        assert bridge.uri == f"ws://localhost:{DEFAULT_PORT}"
        assert bridge.client_name == DEFAULT_CLIENT_NAME

    def test_custom_address_and_client_name_are_used(self) -> None:
        # Arrange / Act
        bridge = DoricoBridge(host="192.168.1.10", port=9999, client_name="my-tool")

        # Assert
        assert bridge.uri == "ws://192.168.1.10:9999"
        assert bridge.client_name == "my-tool"
