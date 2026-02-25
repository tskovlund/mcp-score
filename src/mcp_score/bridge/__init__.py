"""WebSocket bridge for communicating with a live MuseScore instance."""

from mcp_score.bridge.client import MuseScoreBridge

__all__ = ["MuseScoreBridge", "get_bridge"]

_bridge: MuseScoreBridge | None = None


def get_bridge() -> MuseScoreBridge:
    """Get the shared bridge instance, creating one if needed."""
    global _bridge  # noqa: PLW0603
    if _bridge is None:
        _bridge = MuseScoreBridge()
    return _bridge
