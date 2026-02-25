"""WebSocket client for the Sibelius Connect API.

Sibelius 2024.3+ has "Sibelius Connect" — a WebSocket server (default
port 1898, configurable). The protocol uses the same handshake as Dorico —
see ``remote_control.py`` for details.

Sibelius Connect exposes 900+ ManuScript commands. Requires Sibelius
Ultimate tier.

Note: Detailed score reading (individual notes, articulations) requires a
ManuScript file-based bridge — a future enhancement. The WebSocket command
API is focused on score manipulation.
"""

from mcp_score.bridge.remote_control import (
    DEFAULT_CLIENT_NAME,
    HANDSHAKE_VERSION,
    HandshakeError,
    RemoteControlBridge,
)

__all__ = [
    "DEFAULT_CLIENT_NAME",
    "DEFAULT_PORT",
    "HANDSHAKE_VERSION",
    "HandshakeError",
    "SibeliusBridge",
]

#: Default WebSocket port for Sibelius Connect.
DEFAULT_PORT = 1898


class SibeliusBridge(RemoteControlBridge):
    """WebSocket client for the Sibelius Connect API.

    Thin subclass of ``RemoteControlBridge`` that provides Sibelius-specific
    defaults. All protocol logic lives in the base class.
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = DEFAULT_PORT,
        client_name: str = DEFAULT_CLIENT_NAME,
    ) -> None:
        super().__init__("Sibelius", host, port, client_name)
