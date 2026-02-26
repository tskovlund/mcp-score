"""Tests for DoricoBridge — subclass-specific behavior only.

Protocol-level tests (handshake, commands, disconnect, ping, barlines,
limitations) are in test_remote_control_bridge.py.
"""

from __future__ import annotations

from mcp_score.bridge.dorico import DEFAULT_PORT, DoricoBridge


class TestDoricoBridgeDefaults:
    def test_init_sets_default_port(self) -> None:
        # Arrange / Act
        bridge = DoricoBridge()

        # Assert
        assert bridge.port == DEFAULT_PORT
        assert bridge.port == 4560

    def test_application_name_returns_dorico(self) -> None:
        # Arrange / Act
        bridge = DoricoBridge()

        # Assert
        assert bridge.application_name == "Dorico"

    def test_uri_includes_default_port(self) -> None:
        # Arrange / Act
        bridge = DoricoBridge()

        # Assert
        assert bridge.uri == "ws://localhost:4560"

    def test_init_with_custom_values_sets_host_and_port(self) -> None:
        # Arrange / Act
        bridge = DoricoBridge(host="192.168.1.10", port=9999)

        # Assert
        assert bridge.host == "192.168.1.10"
        assert bridge.port == 9999
        assert bridge.uri == "ws://192.168.1.10:9999"
