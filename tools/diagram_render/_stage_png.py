"""Screenshot the .stage element of a self-contained diagram HTML to PNG.
Scratch tooling. Usage: python _stage_png.py <input.html> <output.png>"""
from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright


def main() -> None:
    html = Path(sys.argv[1])
    out = Path(sys.argv[2])
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome")
        page = browser.new_page(viewport={"width": 1320, "height": 1000},
                                device_scale_factor=2)
        page.goto(html.resolve().as_uri(), wait_until="networkidle")
        page.wait_for_timeout(300)
        out.parent.mkdir(parents=True, exist_ok=True)
        page.locator(".stage").screenshot(path=str(out))
        print("wrote", out)
        browser.close()


if __name__ == "__main__":
    main()
