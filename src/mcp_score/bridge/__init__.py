"""Bridges to running score applications.

``ScoreBridge`` is the interface the tools use. ``MuseScoreBridge`` talks
to the bridge plugin inside MuseScore; ``DoricoBridge`` talks to Dorico's
Remote Control API through ``RemoteControlBridge``. ``registry`` tracks
which one is active.
"""

from mcp_score.bridge.base import CommandResult, NoteDuration, ScoreBridge
from mcp_score.bridge.dorico import DoricoBridge
from mcp_score.bridge.musescore import MuseScoreBridge
from mcp_score.bridge.registry import BridgeRegistry, registry
from mcp_score.bridge.remote_control import HandshakeError, RemoteControlBridge
from mcp_score.bridge.websocket import TransportError, WebSocketBridge

__all__ = [
    "BridgeRegistry",
    "CommandResult",
    "DoricoBridge",
    "HandshakeError",
    "MuseScoreBridge",
    "NoteDuration",
    "RemoteControlBridge",
    "ScoreBridge",
    "TransportError",
    "WebSocketBridge",
    "registry",
]
