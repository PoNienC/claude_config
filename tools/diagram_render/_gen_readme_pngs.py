"""Render the operating-model diagram (.stage element) in each highlight state
and drop the PNG into the matching repo's docs/img folder. Scratch tooling."""
from __future__ import annotations

from pathlib import Path

from playwright.sync_api import sync_playwright

HTML = Path("pp_claude_handbook/docs/operating-model.html")

# (highlight state, output PNG path relative to GitHub working dir)
TARGETS = [
    ("all",    "pp_claude_handbook/docs/img/operating-model.png"),
    ("github", "claude_skills/docs/img/operating-model.png"),
    ("skill",  "Urban_Network_Simplification/docs/img/operating-model.png"),
    ("plugin", "pp_core/docs/img/operating-model.png"),
    ("mcp",    "gis_mcp/docs/img/operating-model.png"),
]


def main() -> None:
    url = HTML.resolve().as_uri()
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome")
        page = browser.new_page(viewport={"width": 1320, "height": 1000},
                                device_scale_factor=2)
        page.goto(url, wait_until="networkidle")
        page.wait_for_timeout(300)
        stage = page.locator(".stage")
        for state, out in TARGETS:
            page.evaluate(f"setView('{state}')")
            page.wait_for_timeout(250)
            outp = Path(out)
            outp.parent.mkdir(parents=True, exist_ok=True)
            stage.screenshot(path=str(outp))
            print("wrote", outp)
        browser.close()


if __name__ == "__main__":
    main()
