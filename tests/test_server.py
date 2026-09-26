"""Tests for the assembled MCP server: what it offers and how tools reach it.

The server is built around a bridge registry that its lifespan hands to
every tool through the request context, so these tests build the server
around the test's registry and inject the matching context. A failing
tool raises ``ToolError`` out of ``call_tool``; turning that into an
error response is the SDK's request handler's job, not tested here.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest

from mcp_score.server import SERVER_NAME, create_server
from mcp_score.tools import NOT_CONNECTED, ToolError
from mcp_score.tools.generate import PROMPT_NAME

if TYPE_CHECKING:
    from mcp_score.bridge import BridgeRegistry
    from mcp_score.context import ScoreContext

EXPECTED_TOOLS: frozenset[str] = frozenset(
    {
        # connection
        "connect_to_musescore",
        "disconnect_from_musescore",
        "connect_to_dorico",
        "disconnect_from_dorico",
        "get_live_score_info",
        "ping_score_app",
        # analysis
        "read_passage",
        "get_measure_content",
        "get_selection_properties",
        # manipulation
        "add_live_note",
        "add_live_rehearsal_mark",
        "add_live_chord_symbol",
        "add_live_dynamic",
        "set_live_barline",
        "set_live_key_signature",
        "set_live_time_signature",
        "set_live_tempo",
        "append_live_measures",
        "transpose_passage",
        "undo_last_action",
        # generate
        "generate_score",
        "score_generation_guide",
        # render
        "render_score",
    }
)
"""Every tool the server must offer, across all tool modules."""


class TestCreateServer:
    @pytest.mark.anyio()
    async def test_create_server_registers_every_tool(self) -> None:
        # Arrange
        server = create_server()

        # Act
        tools = await server.list_tools()

        # Assert
        assert server.name == SERVER_NAME
        assert {tool.name for tool in tools} == EXPECTED_TOOLS

    @pytest.mark.anyio()
    async def test_create_server_registers_prompt_under_hyphenated_name(
        self,
    ) -> None:
        # Arrange
        server = create_server()

        # Act
        prompt_names = [prompt.name for prompt in await server.list_prompts()]

        # Assert
        assert prompt_names == [PROMPT_NAME]

    @pytest.mark.anyio()
    async def test_lifespan_yields_state_holding_given_registry(
        self, registry: BridgeRegistry
    ) -> None:
        # Arrange
        server = create_server(registry)
        lifespan = server.settings.lifespan
        assert lifespan is not None

        # Act
        async with lifespan(server) as state:
            # Assert
            assert state.registry is registry

    @pytest.mark.anyio()
    async def test_tool_called_through_server_raises_not_connected(
        self, registry: BridgeRegistry, context: ScoreContext
    ) -> None:
        # Arrange: the fresh registry has nothing connected.
        server = create_server(registry)

        # Act / Assert
        with pytest.raises(ToolError, match=re.escape(NOT_CONNECTED)):
            await server.call_tool("undo_last_action", {}, context=context)
