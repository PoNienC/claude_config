# geoai_mcp

The GeoAI-Architect MCP server. Exposes typed spatial tools to any
MCP-compliant LLM client (Claude Code, Cursor, Codex, custom Strands
agents, MCP Inspector).

This server lives under `~/.claude/mcp_servers/geoai_mcp/` so it
syncs across your machines via the `claude_config` repo.

## What this server provides

| Tool | Purpose | Read/Write |
|---|---|---|
| `geoai_get_crs_info` | Look up CRS metadata by EPSG code | Read-only |
| `geoai_calculate_isochrone` | Compute travel-time polygon around an origin | Read-only |
| `geoai_stac_search` | Search Microsoft Planetary Computer STAC catalogue | Read-only |

Three more tools sketched in `server.py` comments are ready for you
to implement when the workflow demands them: `geoai_overture_fetch`,
`geoai_reproject`, `geoai_spatial_join`.

## One-time setup per machine

### macOS

```bash
cd ~/.claude/mcp_servers/geoai_mcp
python3 -m pip install --user -r requirements.txt
```

### Windows PowerShell

```powershell
cd $HOME\.claude\mcp_servers\geoai_mcp
python -m pip install --user -r requirements.txt
```

After install, fully quit and relaunch Claude Code. The server
registers automatically because `settings.json` declares it.

## Verify the server runs

Standalone (without Claude Code):

```bash
python3 -m server
```

It will appear to hang. That is correct — the server is waiting on
stdin for an MCP client. Press `Ctrl+C` to stop.

With the MCP Inspector (a browser-based UI, no LLM required):

```bash
mcp dev server.py
```

This opens `http://127.0.0.1:6274`. Click `geoai_get_crs_info`, type
`27700` in `epsg_code`, hit Run. You should see British National Grid
metadata.

## Inside Claude Code

After `pip install` and relaunching CC, run:

```
/mcp
```

You should see `geoai` listed with three tools. Then ask:

> Use the geoai MCP server to tell me about EPSG:27700.

A successful response confirms the full stack — MCP transport,
Pydantic validation, pyproj resolution, response formatting — all
working.

## Adding a new tool

1. Create `tools/<your_tool>.py`. Follow the pattern in
   `tools/crs_info.py` (Pydantic input model, @mcp.tool decorator,
   structured return dict).
2. Import it in `server.py` next to the existing tool imports.
3. If the tool takes a CRS argument, add the parameter name to
   `CRS_PARAMETER_NAMES` in `~/.claude/hooks/pre_tool_geoai_validate_crs.py`.
4. If the tool is read-only, add it to `permissions.allow` in
   `~/.claude/settings.json`.
5. Restart Claude Code. The new tool appears in `/mcp`.

## Architecture and safety

- The `safety/sensitive_zones.py` module is shared across tools.
  Every tool that emits coordinates to a third-party service must
  check `is_inside_sensitive_zone()` before egress.
- Backend dispatch via `GEOAI_BACKEND` environment variable (set in
  `settings.json`). Switch between `local`, `onprem`, `cloud` as
  your deployment matures.
- All tools return structured envelopes with either successful
  results or `{"error": "...", "code": "..."}`. Tools must not
  raise exceptions to the MCP framework — exceptions abort the
  call without giving the LLM a chance to reason about the
  failure.

## What is intentionally absent

- No write tools yet. When you add `geoai_postgis_query`, mark it
  with `destructiveHint: True` in its annotations and keep it out
  of `permissions.allow` so every invocation prompts for explicit
  confirmation.
- No production routing engine wired. The `osrm-demo` backend in
  `tools/isochrone.py` returns a placeholder polygon. Replace with
  a self-hosted Valhalla / OSRM / GraphHopper when ready.

## Virtual environment (optional)

For dependency isolation, create a venv instead of using
`pip install --user`:

```bash
cd ~/.claude/mcp_servers/geoai_mcp
python3 -m venv .venv
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\Activate.ps1  # Windows PowerShell
pip install -r requirements.txt
```

Then override `command` in your `settings.local.json` (not
`settings.json` — settings.local.json is per-machine and gitignored)
to point at the venv's Python:

```json
{
  "mcpServers": {
    "geoai": {
      "command": "/Users/po.nienchen/.claude/mcp_servers/geoai_mcp/.venv/bin/python"
    }
  }
}
```

For personal use, `pip install --user` is simpler and works fine.
