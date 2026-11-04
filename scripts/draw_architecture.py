"""Render docs/img/architecture.mmd to the light and dark PNGs the README shows.

The README uses images rather than a Mermaid block because GitHub draws its zoom and pan controls over Mermaid diagrams,
and a wide diagram is shrunk until its text is hard to read. Run this after editing the .mmd file.

Needs Playwright and its Chromium (`pip install playwright`, `playwright install chromium`), which the app itself does
not, and internet access for Mermaid.

Usage:  python scripts/draw_architecture.py
"""

from __future__ import annotations

from pathlib import Path

from playwright.sync_api import sync_playwright

IMG = Path(__file__).resolve().parent.parent / "docs" / "img"
MERMAID = "https://cdn.jsdelivr.net/npm/mermaid@11.4.1/dist/mermaid.min.js"
SCALE = 2  # stays sharp on high-density screens
FONT = "-apple-system, 'Segoe UI', Helvetica, Arial, sans-serif"
# Muted colours that sit on GitHub's own light and dark page backgrounds; the images are transparent around the boxes.
THEMES = {
    "light": {"primaryColor": "#f6f8fa", "primaryBorderColor": "#8c959f", "primaryTextColor": "#1f2328",
              "lineColor": "#59636e", "secondaryColor": "#f6f8fa", "tertiaryColor": "#ffffff",
              "clusterBkg": "#eaeef2", "clusterBorder": "#afb8c1", "edgeLabelBackground": "#ffffff"},
    "dark": {"primaryColor": "#21262d", "primaryBorderColor": "#6e7681", "primaryTextColor": "#e6edf3",
             "lineColor": "#9198a1", "secondaryColor": "#21262d", "tertiaryColor": "#0d1117",
             "clusterBkg": "#161b22", "clusterBorder": "#3d444d", "edgeLabelBackground": "#0d1117"},
}


def main() -> None:
    source = (IMG / "architecture.mmd").read_text(encoding="utf-8")
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for name, colours in THEMES.items():
            page = browser.new_page(viewport={"width": 1400, "height": 1400}, device_scale_factor=SCALE)
            page.set_content("<!doctype html><body style='margin:0;background:transparent'><div id=out></div></body>")
            page.add_script_tag(url=MERMAID)
            page.evaluate("""async ([src, colours, font]) => {
              mermaid.initialize({startOnLoad: false, theme: 'base', flowchart: {useMaxWidth: false, wrappingWidth: 320},
                                  themeVariables: {...colours, fontFamily: font, fontSize: '16px'}});
              const {svg} = await mermaid.render('diagram', src);
              document.getElementById('out').innerHTML = svg;
            }""", [source, colours, FONT])
            out = IMG / f"architecture-{name}.png"
            page.locator("#out svg").screenshot(path=out, omit_background=True)
            print(f"{out.name}: {out.stat().st_size // 1024} KB")
        browser.close()


if __name__ == "__main__":
    main()
