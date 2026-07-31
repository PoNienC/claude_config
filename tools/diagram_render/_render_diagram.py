"""Render a self-contained HTML diagram to a high-DPI PNG via system Chrome.

Scratch tooling (lives at the GitHub working-dir root, outside every repo).
Usage:
    python _render_diagram.py <input.html> <output.png> [width]
"""
from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright


def render(html: Path, png: Path, width: int = 1300) -> None:
    url = html.resolve().as_uri()
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome")
        page = browser.new_page(viewport={"width": width, "height": 1000},
                                device_scale_factor=2)
        page.goto(url, wait_until="networkidle")
        page.wait_for_timeout(350)  # let webfont fallback + script settle
        png.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(png), full_page=True)
        browser.close()
    print(f"rendered {png}")


if __name__ == "__main__":
    src = Path(sys.argv[1])
    out = Path(sys.argv[2])
    w = int(sys.argv[3]) if len(sys.argv) > 3 else 1300
    render(src, out, w)
