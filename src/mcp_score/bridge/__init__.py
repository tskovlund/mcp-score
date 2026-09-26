"""Bridges to running score applications.

``ScoreBridge`` is the interface the tools use, and ``results`` holds the
models its operations return. ``MuseScoreBridge`` talks to the bridge
plugin inside MuseScore; ``DoricoBridge`` talks to Dorico's Remote
Control API through ``RemoteControlBridge``. A ``BridgeRegistry`` tracks
which one is active.
"""

from mcp_score.bridge.base import BridgeError, CommandResult, ScoreBridge
from mcp_score.bridge.dorico import DoricoBridge
from mcp_score.bridge.musescore import MuseScoreBridge
from mcp_score.bridge.registry import BridgeRegistry
from mcp_score.bridge.remote_control import HandshakeError, RemoteControlBridge
from mcp_score.bridge.websocket import TransportError, WebSocketBridge

__all__ = [
    "BridgeError",
    "BridgeRegistry",
    "CommandResult",
    "DoricoBridge",
    "HandshakeError",
    "MuseScoreBridge",
    "RemoteControlBridge",
    "ScoreBridge",
    "TransportError",
    "WebSocketBridge",
]
