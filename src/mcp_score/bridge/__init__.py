"""Bridge registry — manages connections to score notation applications.

Only one bridge (MuseScore, Dorico, etc.) is active at a time.
Tools use ``get_active_bridge()`` to get the currently connected bridge.
Connection tools call ``set_active_bridge()`` to switch.
"""

from mcp_score.bridge.base import ScoreBridge
from mcp_score.bridge.dorico import DoricoBridge
from mcp_score.bridge.musescore import MuseScoreBridge

__all__ = [
    "DoricoBridge",
    "MuseScoreBridge",
    "ScoreBridge",
    "get_active_bridge",
    "get_dorico_bridge",
    "get_musescore_bridge",
    "set_active_bridge",
]

_active_bridge: ScoreBridge | None = None

# Singletons — one instance per DAW type, created on first use.
_musescore_bridge: MuseScoreBridge | None = None
_dorico_bridge: DoricoBridge | None = None


def get_musescore_bridge() -> MuseScoreBridge:
    """Get the shared MuseScore bridge instance, creating one if needed."""
    global _musescore_bridge  # noqa: PLW0603
    if _musescore_bridge is None:
        _musescore_bridge = MuseScoreBridge()
    return _musescore_bridge


def get_dorico_bridge() -> DoricoBridge:
    """Get the shared Dorico bridge instance, creating one if needed."""
    global _dorico_bridge  # noqa: PLW0603
    if _dorico_bridge is None:
        _dorico_bridge = DoricoBridge()
    return _dorico_bridge


def get_active_bridge() -> ScoreBridge | None:
    """Return the currently active bridge, or ``None`` if nothing is connected."""
    return _active_bridge


def set_active_bridge(bridge: ScoreBridge | None) -> None:
    """Set the active bridge.

    Pass ``None`` to clear the active bridge (e.g. on disconnect).
    """
    global _active_bridge  # noqa: PLW0603
    _active_bridge = bridge
