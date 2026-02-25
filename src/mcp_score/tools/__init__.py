"""MCP tool definitions for live score interaction."""

import json
from typing import Any

from mcp_score.bridge import ScoreBridge, get_active_bridge

__all__ = ["NOT_CONNECTED", "check_measure", "connected_bridge", "to_json"]

NOT_CONNECTED = (
    "Not connected to any score application. "
    "Use connect_to_musescore or connect_to_dorico first."
)


def to_json(data: dict[str, Any]) -> str:
    """Serialize a result dict to a JSON string for MCP tool responses."""
    return json.dumps(data)


def connected_bridge() -> ScoreBridge | None:
    """Return the active bridge if connected, or ``None``.

    Tools that require an active connection should call this and return
    an error when ``None`` is returned::

        bridge = connected_bridge()
        if bridge is None:
            return to_json({"error": NOT_CONNECTED})
    """
    bridge = get_active_bridge()
    if bridge is None:
        return None
    return bridge if bridge.is_connected else None


def check_measure(measure: int, name: str = "measure") -> str | None:
    """Return an error JSON string if *measure* is < 1, else ``None``."""
    if measure < 1:
        return to_json({"error": f"{name} must be >= 1."})
    return None
