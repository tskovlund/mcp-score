"""WebSocket client for the Dorico Remote Control API.

Dorico 4+ has a built-in WebSocket server (default port 4560). The protocol
uses a two-step handshake — see ``remote_control.py`` for details.

Protocol details reverse-engineered from github.com/scott-janssens/Dorico.Net.
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
    "DoricoBridge",
    "HANDSHAKE_VERSION",
    "HandshakeError",
]

#: Default WebSocket port for Dorico's Remote Control server.
DEFAULT_PORT = 4560


class DoricoBridge(RemoteControlBridge):
    """WebSocket client for the Dorico Remote Control API.

    Thin subclass of ``RemoteControlBridge`` that provides Dorico-specific
    defaults. All protocol logic lives in the base class.
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = DEFAULT_PORT,
        client_name: str = DEFAULT_CLIENT_NAME,
    ) -> None:
        super().__init__("Dorico", host, port, client_name)
