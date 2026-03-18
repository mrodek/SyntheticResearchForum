"""SRF MCP server — stdio entry point for Claude Desktop.

Run directly:
    python src/srf/mcp/server.py

Or register in claude_desktop_config.json (see Requirements/INTEGRATION_GUIDE.md).
"""

from __future__ import annotations

import asyncio
import json

import mcp.types as types
from mcp.server import Server
from mcp.server.stdio import stdio_server

from srf.mcp.tools import SRF_MCP_TOOLS, trigger_newsletter_forum

app = Server("srf")


@app.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name=t["name"],
            description=t["description"],
            inputSchema=t["parameters"],
        )
        for t in SRF_MCP_TOOLS
    ]


@app.call_tool()
async def call_tool(
    name: str,
    arguments: dict,
) -> list[types.TextContent]:
    if name == "trigger_newsletter_forum":
        result = await trigger_newsletter_forum(**arguments)
        return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
    raise ValueError(f"Unknown tool: {name}")


async def main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())
