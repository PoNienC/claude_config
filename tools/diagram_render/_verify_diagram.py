"""Verify the diagram: element-level screenshots of the .stage in several
highlight states. Scratch tooling."""
from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright


def verify(html: Path, outdir: Path, states: list[str]) -> None:
    url = html.resolve().as_uri()
    outdir.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome")
        page = browser.new_page(viewport={"width": 1320, "height": 1000},
                                device_scale_factor=2)
        page.goto(url, wait_until="networkidle")
        page.wait_for_timeout(300)
        stage = page.locator(".stage")
        for st in states:
            page.evaluate(f"setView('{st}')")
            page.wait_for_timeout(250)
            out = outdir / f"stage_{st}.png"
            stage.screenshot(path=str(out))
            print("wrote", out)
        browser.close()


if __name__ == "__main__":
    src = Path(sys.argv[1])
    verify(src, Path("_preview"), ["all", "github", "skill", "mcp", "plugin"])
