"""Bridge to Dorico's Remote Control API (experimental).

Dorico 4 and later serve the Remote Control protocol on port 4560 by
default; no plugin is needed. Support is experimental: the API is
undocumented and command-only, and this bridge has not been verified
against a running Dorico. Protocol details come from
github.com/scott-janssens/Dorico.Net.
"""

from mcp_score.bridge.remote_control import DEFAULT_CLIENT_NAME, RemoteControlBridge
from mcp_score.bridge.websocket import DEFAULT_HOST

__all__ = ["DEFAULT_PORT", "DoricoBridge"]

DEFAULT_PORT = 4560
"""Dorico's default Remote Control port; configurable in its preferences."""

APPLICATION_NAME = "Dorico"


class DoricoBridge(RemoteControlBridge):
    """Remote Control bridge with Dorico's defaults."""

    def __init__(
        self,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        client_name: str = DEFAULT_CLIENT_NAME,
    ) -> None:
        super().__init__(APPLICATION_NAME, host, port, client_name)
