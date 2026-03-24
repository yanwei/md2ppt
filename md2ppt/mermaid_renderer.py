"""Server-side Mermaid diagram rendering via Playwright.

All diagrams are rendered in a single headless Chromium session so every
diagram type (flowchart, sequence, class, …) uses identical font settings.
Two theme variants (neutral / dark) are rendered per diagram so the
presentation can switch between light and dark mode without re-rendering.

Falls back silently to client-side rendering if Playwright is not installed
or Chromium is unavailable.
"""
from __future__ import annotations

import json
import re

_MERMAID_DIV_RE = re.compile(r'<div class="mermaid">([\s\S]*?)</div>')

# Must match generator.py's body font-family exactly.
_FONT_FAMILY = (
    "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, "
    "'Helvetica Neue', Arial, sans-serif"
)

# HTML page template: {theme_json} and {bg} are substituted per render pass.
_PAGE_TEMPLATE = """\
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body {{ margin: 0; background: {bg}; font-family: {font}; }}
  .mermaid {{ display: block; padding: 16px; }}
</style>
</head>
<body>
{placeholders}
<script>
const sources = {sources_json};
sources.forEach((src, i) => {{
  document.getElementById('m' + i).textContent = src;
}});
</script>
<script type="module">
import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs';
mermaid.initialize({{
  startOnLoad: false,
  theme: {theme_json},
  flowchart: {{ htmlLabels: false }},
  sequence: {{
    htmlLabels: false,
    actorFontSize:   16,
    messageFontSize: 16,
    noteFontSize:    16,
  }},
  themeVariables: {{
    fontFamily: {font_json},
    fontSize:   '16px',
  }},
}});
await mermaid.run({{ querySelector: '.mermaid' }});
window.__mermaidDone__ = true;
</script>
</body>
</html>
"""


def replace_mermaid_with_svg(slides: list[str]) -> tuple[list[str], bool]:
    """Replace <div class="mermaid"> blocks with dual-theme inline SVGs.

    Each diagram is replaced by a <div class="mermaid-rendered"> containing
    two <img> tags: one for light mode (.diagram-light) and one for dark mode
    (.diagram-dark).  CSS in generator.py shows/hides the appropriate one.

    Returns:
        (processed_slides, has_client_side_fallback)
    """
    all_sources: list[str] = []
    slide_indices: list[list[int]] = []

    for slide_html in slides:
        matches = list(_MERMAID_DIV_RE.finditer(slide_html))
        idxs = []
        for m in matches:
            idxs.append(len(all_sources))
            all_sources.append(m.group(1))
        slide_indices.append(idxs)

    if not all_sources:
        return slides, False

    light_svgs, dark_svgs = _render_both_themes(all_sources)

    if light_svgs is None:
        return slides, True

    result: list[str] = []
    has_fallback = False

    for slide_html, idxs in zip(slides, slide_indices):
        if not idxs:
            result.append(slide_html)
            continue

        counter = [0]

        def _replacer(m: re.Match) -> str:
            global_idx = idxs[counter[0]]
            counter[0] += 1
            light = light_svgs[global_idx]
            dark  = dark_svgs[global_idx] if dark_svgs else None
            if light is None:
                nonlocal has_fallback
                has_fallback = True
                return m.group(0)
            light_img = _svg_to_img(light, css_class='diagram-light')
            # Fall back to inverted light SVG if dark render failed.
            dark_img  = _svg_to_img(dark if dark else light, css_class='diagram-dark')
            return f'<div class="mermaid-rendered">{light_img}{dark_img}</div>'

        result.append(_MERMAID_DIV_RE.sub(_replacer, slide_html))

    return result, has_fallback


def _render_both_themes(
    sources: list[str],
) -> tuple[list[str | None] | None, list[str | None] | None]:
    """Render each diagram in neutral (light) and dark themes.

    Both renders share one browser process; the CDN is cached after the first
    page load so the second page loads significantly faster.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None, None

    placeholders = '\n'.join(
        f'<div class="mermaid" id="m{i}"></div>'
        for i in range(len(sources))
    )
    common = dict(
        font=_FONT_FAMILY,
        font_json=json.dumps(_FONT_FAMILY),
        placeholders=placeholders,
        sources_json=json.dumps(sources),
    )

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch()

            n = len(sources)
            light_svgs = _render_page(
                browser, _PAGE_TEMPLATE.format(theme_json='"neutral"', bg='white', **common), n
            )
            dark_svgs = _render_page(
                browser, _PAGE_TEMPLATE.format(theme_json='"dark"',    bg='#1e1e2e', **common), n
            )

            browser.close()
            return light_svgs, dark_svgs
    except Exception:
        return None, None


def _render_page(browser, page_html: str, n: int) -> list[str | None]:
    """Load page_html in a new browser page, wait for Mermaid, extract n SVGs."""
    page = browser.new_page(viewport={"width": 1600, "height": 900})
    try:
        page.set_content(page_html, wait_until="networkidle")
        page.wait_for_function("window.__mermaidDone__ === true", timeout=20_000)
        svgs: list[str | None] = []
        for i in range(n):
            el = page.query_selector(f"#m{i} svg")
            # Return raw SVG outerHTML; _svg_to_img is called by the caller.
            svgs.append(el.evaluate("el => el.outerHTML") if el else None)
        return svgs
    except Exception:
        return [None] * n
    finally:
        page.close()


def _svg_to_img(svg: str, *, css_class: str = '') -> str:
    """Embed SVG as a data-URI <img> tag (CSS-isolated, correct intrinsic size).

    • Adds xmlns so the SVG renders as a standalone document in data-URI context.
    • Replaces Mermaid's width="100%" with explicit px from viewBox so browsers
      compute a consistent intrinsic size (avoids apparent font-size differences).
    • Clears background rects so the SVG is transparent over the slide.
    """
    import base64

    if 'xmlns=' not in svg:
        svg = svg.replace('<svg ', '<svg xmlns="http://www.w3.org/2000/svg" ', 1)

    # Resolve width="100%" → explicit px from viewBox.
    vbox = re.search(r'viewBox=["\'][^"\']*?\s+([0-9.]+)\s+([0-9.]+)["\']', svg)
    if vbox:
        vb_w = int(float(vbox.group(1)))
        vb_h = int(float(vbox.group(2)))
        svg = re.sub(r'\bwidth="100%"', f'width="{vb_w}"', svg)
        if not re.search(r'\bheight="[0-9]', svg):
            svg = re.sub(r'(<svg\b)', rf'\1 height="{vb_h}"', svg, count=1)

    # Clear white background rects so the SVG is transparent.
    svg = re.sub(
        r'(<rect\b[^>]*\bclass="[^"]*\bbackground\b[^"]*")',
        r'\1 fill="none"',
        svg,
    )

    class_attr = f' class="{css_class}"' if css_class else ''
    data = base64.b64encode(svg.encode('utf-8')).decode('ascii')
    # No display:block in inline style — visibility is controlled by CSS rules
    # in generator.py so that diagram-dark can be hidden via display:none.
    return (
        f'<img{class_attr} src="data:image/svg+xml;base64,{data}" '
        'style="max-width:100%;height:auto;margin:0 auto;" '
        'alt="diagram">'
    )
