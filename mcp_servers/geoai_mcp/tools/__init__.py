"""GeoAI MCP tools.

Each tool is a Python module that registers one tool with the FastMCP
server via the @mcp.tool() decorator. Add new tools by creating a new
module here and importing it in `server.py`.

Naming convention:
    File:           crs_info.py
    Tool function:  geoai_get_crs_info
    File pattern:   snake_case, no `geoai_` prefix on filename
    Tool name:      snake_case, geoai_ prefix on tool name
"""
