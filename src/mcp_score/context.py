"""What a tool receives from the server: the application state.

The MCP SDK injects a `Context` into every tool that declares one, and
the server's lifespan hands it the state below. Tools reach the bridge
registry through it, so nothing in the package is a module-level
singleton and a test can build a server around any registry.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from mcp.server.mcpserver import Context

if TYPE_CHECKING:
    from mcp_score.bridge import BridgeRegistry

__all__ = ["AppState", "ScoreContext", "registry_of"]


@dataclass(frozen=True)
class AppState:
    """State that lives for the server's lifetime."""

    registry: BridgeRegistry
    """The bridges to the score applications, and which one is active."""


ScoreContext = Context[AppState, Any]
"""The context every bridge-using tool declares as its first parameter.

A plain assignment rather than a ``type`` statement, because the SDK
recognises the parameter to inject by ``issubclass(annotation, Context)``.
"""


def registry_of(context: ScoreContext) -> BridgeRegistry:
    """The server's bridge registry."""
    return context.request_context.lifespan_context.registry
