"""Tests for SibeliusBridge — subclass-specific behavior only.

Protocol-level tests (handshake, commands, disconnect, ping, barlines,
limitations) are in test_remote_control_bridge.py.
"""

from __future__ import annotations

from mcp_score.bridge.sibelius import DEFAULT_PORT, SibeliusBridge


class TestSibeliusBridgeDefaults:
    def test_init_sets_default_port(self) -> None:
        # Arrange / Act
        bridge = SibeliusBridge()

        # Assert
        assert bridge.port == DEFAULT_PORT
        assert bridge.port == 1898

    def test_application_name_returns_sibelius(self) -> None:
        # Arrange / Act
        bridge = SibeliusBridge()

        # Assert
        assert bridge.application_name == "Sibelius"

    def test_uri_includes_default_port(self) -> None:
        # Arrange / Act
        bridge = SibeliusBridge()

        # Assert
        assert bridge.uri == "ws://localhost:1898"

    def test_init_with_custom_values_sets_host_and_port(self) -> None:
        # Arrange / Act
        bridge = SibeliusBridge(host="192.168.1.10", port=9999)

        # Assert
        assert bridge.host == "192.168.1.10"
        assert bridge.port == 9999
        assert bridge.uri == "ws://192.168.1.10:9999"
