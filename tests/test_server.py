"""Tests for MCP server initialization."""

from mcp_score.server import mcp


class TestServer:
    def test_server_name_is_mcp_score(self) -> None:
        # Arrange / Act
        name = mcp.name

        # Assert
        assert name == "mcp-score"
