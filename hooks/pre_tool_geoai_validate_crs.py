#!/usr/bin/env python3
"""
pre_tool_geoai_validate_crs.py — Cross-platform CRS validation Hook.

WHEN THIS FIRES:
    PreToolUse on any tool matching `mcp__geoai__.*` (see settings.json).

WHAT IT DOES:
    1. Reads the JSON tool-call payload from stdin.
    2. Looks for any parameter whose name suggests a CRS argument
       (target_crs, source_crs, output_crs, crs, target_epsg,
       source_epsg, epsg_code).
    3. Validates each via pyproj.
    4. Exits non-zero (with feedback) if any CRS is invalid.

WHY PYTHON RATHER THAN .sh + .ps1:
    The geoai MCP server already requires Python with pyproj installed
    on both machines. Using Python for the hook keeps a single source
    of truth, eliminates Bash/PowerShell parity drift, and works
    identically on macOS, Linux, and Windows. Your sync_guide.md
    mentions creating PowerShell siblings for shell hooks — that
    approach is correct for hooks that are inherently shell, but for
    hooks that already depend on Python it adds maintenance burden
    with no benefit.

EXIT CODES:
    0  — allow the tool call (no CRS args, or all CRS args valid).
    2  — deny the tool call with feedback to the agent (invalid CRS).
    Any other non-zero — treated as "fail open" by Claude Code: the
                          tool call proceeds, but stderr is logged.

INSTALLATION:
    Wired in settings.json:
        {
          "hooks": {
            "PreToolUse": [{
              "matcher": "mcp__geoai__.*",
              "hooks": [{
                "type": "command",
                "command": "python3 ${HOME}/.claude/hooks/pre_tool_geoai_validate_crs.py"
              }]
            }]
          }
        }
    On Windows, `python3` may be aliased to `python`. If `python3` is
    not on PATH, change to `python` in your settings.local.json.
"""

from __future__ import annotations

import json
import sys

# Parameter names treated as CRS arguments. Extend this list when
# introducing tools that use different field names for CRS.
CRS_PARAMETER_NAMES = frozenset({
    "target_crs",
    "source_crs",
    "output_crs",
    "crs",
    "target_epsg",
    "source_epsg",
    "epsg_code",
})


def main() -> int:
    # Read the hook payload from stdin. Claude Code sends a JSON object
    # like:
    #   {"tool_name": "geoai_calculate_isochrone",
    #    "tool_input": {"origin_lon": -0.1, "origin_lat": 51.5, ...}}
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        # If we cannot parse the payload, fail open. Logging the issue
        # is the harness's responsibility; we should not block legitimate
        # tool calls because of a malformed payload from upstream.
        print(
            "WARNING: pre_tool_geoai_validate_crs received unparseable "
            "JSON on stdin; allowing tool call through.",
            file=sys.stderr,
        )
        return 0

    tool_input = payload.get("tool_input", {}) or {}

    # Collect any CRS-related arguments the tool is being called with.
    crs_args = {
        name: value
        for name, value in tool_input.items()
        if name in CRS_PARAMETER_NAMES and value is not None
    }

    # No CRS arguments? Nothing to validate; allow through.
    if not crs_args:
        return 0

    # Lazy import of pyproj. If the user has not yet installed
    # requirements for the MCP server, the hook should fail open with a
    # clear stderr message rather than block all geoai tools.
    try:
        from pyproj import CRS
    except ImportError:
        print(
            "WARNING: pyproj not installed; CRS validation skipped. "
            "Run: pip install pyproj",
            file=sys.stderr,
        )
        return 0

    # Validate each CRS argument. Collect failures so we can report
    # them all at once rather than blocking on the first.
    invalid: list[tuple[str, str, str]] = []
    for name, value in crs_args.items():
        try:
            CRS.from_user_input(value)
        except Exception as exc:  # pylint: disable=broad-except
            invalid.append((name, str(value), str(exc)))

    if invalid:
        print("BLOCKED by pre_tool_geoai_validate_crs:", file=sys.stderr)
        for name, value, err in invalid:
            print(f"  {name}={value!r}: {err}", file=sys.stderr)
        print(
            "Suggestion: call geoai_get_crs_info first to verify the "
            "CRS, or pass a well-known code such as 4326 (WGS84), "
            "27700 (British National Grid), 3857 (Web Mercator), "
            "or 5070 (NAD83 Albers).",
            file=sys.stderr,
        )
        # Exit code 2 = deny tool call with feedback to the agent.
        # The agent sees the stderr message and can correct course.
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
