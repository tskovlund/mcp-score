"""Tests for the assembled MCP server: what it offers and how tools reach it."""

from __future__ import annotations

import json

import pytest
from mcp.types import CallToolResult, TextContent

from mcp_score.server import SERVER_NAME, create_server
from mcp_score.tools import NOT_CONNECTED
from mcp_score.tools.generate import PROMPT_NAME

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
    async def test_tool_called_through_server_returns_not_connected_error(
        self,
    ) -> None:
        # Arrange: the autouse registry fixture leaves nothing connected.
        server = create_server()

        # Act
        result = await server.call_tool("undo_last_action", {})

        # Assert
        assert isinstance(result, CallToolResult)
        assert result.is_error is False
        text_blocks = [
            block for block in result.content if isinstance(block, TextContent)
        ]
        assert len(text_blocks) == 1
        assert json.loads(text_blocks[0].text) == {"error": NOT_CONNECTED}
        assert result.structured_content == {"result": {"error": NOT_CONNECTED}}
