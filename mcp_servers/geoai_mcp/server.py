"""
GeoAI-Architect MCP Server — entry point.

This file is the heart of the framework. When Claude Code (or any
other MCP-compliant client) launches the geoai server, it executes
this file. The server runs as a long-lived subprocess, communicating
with the LLM client over stdin/stdout (the "stdio" transport).

What MCP actually does, in one paragraph:
    The LLM client sends JSON-RPC requests like "list your tools" and
    "call this tool with these arguments". This server replies with
    JSON envelopes describing tool schemas or returning tool results.
    The LLM never executes code on your machine directly — it only
    *requests* tool calls, and this server *executes* them under your
    deterministic control. That separation is what makes MCP safer
    than letting an LLM run arbitrary Python.

Why FastMCP:
    FastMCP is a thin layer over the official `mcp` Python SDK. It
    lets you register tools by decorating regular Python functions.
    The function signature, type hints, and docstring become the
    schema the LLM reads to learn how to call the tool. No manual
    JSON Schema authoring required.

Run it standalone (for testing):
    python3 -m server          # raw run, hangs waiting for client
    mcp dev server.py          # run with the MCP Inspector UI

Inside Claude Code, this server is launched automatically per the
mcpServers.geoai entry in ~/.claude/settings.json. PYTHONPATH is set
so the `from server import mcp` import in each tool resolves.
"""

from mcp.server.fastmcp import FastMCP

# ---------------------------------------------------------------------------
# Server initialisation
# ---------------------------------------------------------------------------
# The string "geoai_mcp" is the server name. Two conventions are at play:
#   1. MCP server-naming convention (snake_case, suffix _mcp): "geoai_mcp".
#   2. Tool prefix when the LLM lists tools: each tool registered below
#      will appear as `geoai_<tool_name>` because we give each tool a
#      name with that prefix.
# Keeping the prefix consistent prevents tool-name collisions when you
# have multiple MCP servers attached to the same Claude session.
mcp = FastMCP("geoai_mcp")


# ---------------------------------------------------------------------------
# Tool registration
# ---------------------------------------------------------------------------
# Each tool lives in its own module under `tools/` for clarity. We
# import them here so the @mcp.tool() decorators inside each module
# run at import time and register the tool with the server.
#
# Order of imports does not affect tool listing order, but grouping by
# capability (info → data → process → AI → output) makes the codebase
# easier to navigate.
from tools import crs_info       # noqa: F401  --  CRS metadata
from tools import isochrone      # noqa: F401  --  routing example
from tools import stac_search    # noqa: F401  --  satellite imagery search

# Future tools you will add. Create the module under `tools/`,
# follow the pattern in `tools/crs_info.py`, then uncomment one
# of these import lines:
#
# from tools import overture_fetch   # global vector substrate
# from tools import reproject        # CRS transformation
# from tools import spatial_join     # vector spatial joins
# from tools import geoai_detect     # object detection via geoai-py
# from tools import geoai_segment    # segmentation via geoai-py
# from tools import viewshed         # 3D viewshed
# from tools import postgis_query    # SQL with safety guards


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    # `transport="stdio"` is correct for personal local use:
    #   - The LLM client launches this script as a subprocess.
    #   - JSON-RPC messages travel over the subprocess's stdin/stdout.
    #   - No network ports, no auth complexity.
    #
    # When you later move to on-premise or cloud deployment with multiple
    # users, switch to `transport="streamable-http"` and configure auth.
    # The tool functions themselves do not change — only this line.
    mcp.run(transport="stdio")
