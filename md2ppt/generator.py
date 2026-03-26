import re as _re
import html as _html
from md2ppt.parser import get_highlight_css
from md2ppt.mermaid_renderer import replace_mermaid_with_svg

_H1_RE = _re.compile(r'<h1>.*?</h1>', _re.DOTALL)


def generate_html(slides: list[str], title: str = "Presentation", author: str = "") -> str:
    # Pre-render Mermaid diagrams to inline SVG (requires Playwright).
    # Falls back to client-side rendering transparently if unavailable.
    slides, needs_mermaid_js = replace_mermaid_with_svg(slides)

    slides_html = ""
    for i, slide_content in enumerate(slides):
        extra_class = " active" if i == 0 else ""
        if i == 0:
            extra_class += " slide-title"
            # Title slide: keep everything in slide-inner (centered layout)
            slides_html += f'    <div class="slide{extra_class}" id="slide-{i}">\n'
            slides_html += f'      <div class="slide-inner">{slide_content}</div>\n'
            slides_html += "    </div>\n"
        else:
            # Content slides: split h1 into a fixed header above the scroll area
            m = _H1_RE.search(slide_content)
            if m:
                h1_html = m.group(0)
                body_html = slide_content[:m.start()] + slide_content[m.end():]
            else:
                h1_html = ""
                body_html = slide_content
            slides_html += f'    <div class="slide{extra_class}" id="slide-{i}">\n'
            slides_html += f'      <div class="slide-header">{h1_html}</div>\n'
            slides_html += f'      <div class="slide-inner">{body_html}</div>\n'
            slides_html += "    </div>\n"

    total = len(slides)
    author_html = f'<span class="ppt-author">Created by {_html.escape(author)}</span><span class="ppt-author-sep"></span>' if author else ""
    highlight_css = get_highlight_css()

    # Build the Mermaid script block only when client-side fallback is needed.
    if needs_mermaid_js:
        mermaid_script_block = """\
  <!-- Mermaid.js for client-side diagram rendering (Playwright was unavailable) -->
  <script type="module">
    import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs';

    document.querySelectorAll('.mermaid').forEach(el => {
      el.dataset.src = el.textContent.trim();
    });

    async function renderMermaid() {
      const stageFs = parseFloat(getComputedStyle(document.getElementById('stage')).fontSize);
      const bodyFs  = Math.round(stageFs * 1.6);

      document.querySelectorAll('.mermaid').forEach(el => {
        el.removeAttribute('data-processed');
        el.innerHTML = el.dataset.src;
      });

      mermaid.initialize({
        startOnLoad: false,
        theme: 'neutral',
        themeVariables: {
          fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif",
        },
      });
      await mermaid.run({ querySelector: '.mermaid' });

      document.querySelectorAll('.mermaid svg').forEach(svg => {
        svg.removeAttribute('width');
        svg.removeAttribute('height');
        svg.style.maxWidth = '100%';
        svg.style.height   = 'auto';
        svg.style.display  = 'block';
        svg.style.margin   = '0 auto';
      });
    }

    await renderMermaid();

    let _mermaidTimer;
    new ResizeObserver(() => {
      clearTimeout(_mermaidTimer);
      _mermaidTimer = setTimeout(renderMermaid, 200);
    }).observe(document.getElementById('stage'));
  </script>"""
    else:
        mermaid_script_block = ""

    return f"""<!DOCTYPE html>
<html lang="zh">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{_html.escape(title)}</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16/dist/katex.min.css">
  <style>
    *, *::before, *::after {{
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }}

    html, body {{
      width: 100%;
      height: 100%;
      background: #0f172a;
      display: flex;
      align-items: center;
      justify-content: center;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto,
                   'Helvetica Neue', Arial, sans-serif;
      overflow: hidden;
    }}

    /* ── Stage: maintains 16:9 ratio ── */
    #stage {{
      position: relative;
      width: min(100vw, calc(100vh * 16 / 9));
      height: min(100vh, calc(100vw * 9 / 16));
      overflow: hidden;
      /* Base unit = 1% of slide width, so all em-based sizes scale with the slide */
      font-size: min(1vw, calc(1vh * 16 / 9));
    }}

    /* ── Slides ── */
    .slide {{
      position: absolute;
      inset: 0;
      background: #ffffff;
      pointer-events: none;
      transform: translateX(100%);
      transition: transform 0.42s cubic-bezier(0.25, 0.46, 0.45, 0.94);
      will-change: transform;
      overflow: hidden;
      display: flex;
      flex-direction: column;
    }}

    .slide.active {{
      transform: translateX(0);
      pointer-events: auto;
    }}

    /* Accent bar at top */
    .slide::before {{
      content: "";
      display: block;
      height: 4px;
      flex-shrink: 0;
      background: linear-gradient(90deg, #3b82f6 0%, #06b6d4 50%, #8b5cf6 100%);
    }}

    /* ── Fixed slide header (title + divider line) ── */
    .slide-header {{
      flex-shrink: 0;
      padding: 3% 7% 0;
      background: #ffffff;
    }}

    .slide-header h1 {{
      font-size: 3.8em;
      font-weight: 700;
      color: #0f172a;
      letter-spacing: -0.02em;
      line-height: 1.2;
      margin: 0;
      padding-bottom: 0.35em;
      border-bottom: 2px solid #e2e8f0;
    }}

    .slide-inner {{
      flex: 1;
      overflow-y: auto;
      padding: 3% 7% 5%;
      /* Custom scrollbar */
      scrollbar-width: thin;
      scrollbar-color: #cbd5e1 transparent;
    }}

    .slide-inner::-webkit-scrollbar {{
      width: 6px;
    }}
    .slide-inner::-webkit-scrollbar-track {{
      background: transparent;
    }}
    .slide-inner::-webkit-scrollbar-thumb {{
      background: #cbd5e1;
      border-radius: 3px;
    }}

    /* ── Typography (all em = % of slide width via #stage base font-size) ── */
    .slide-inner h1 {{
      font-size: 3.8em;
      font-weight: 700;
      color: #0f172a;
      letter-spacing: -0.02em;
      line-height: 1.2;
      margin-bottom: 0.5em;
      padding-bottom: 0.35em;
      border-bottom: 2px solid #e2e8f0;
    }}

    .slide-inner h2 {{
      font-size: 2.4em;
      font-weight: 600;
      color: #1e40af;
      margin-top: 1em;
      margin-bottom: 0.4em;
    }}

    .slide-inner h3 {{
      font-size: 1.9em;
      font-weight: 600;
      color: #334155;
      margin-top: 0.8em;
      margin-bottom: 0.35em;
    }}

    .slide-inner p {{
      font-size: 1.6em;
      color: #334155;
      line-height: 1.75;
      margin-bottom: 0.7em;
    }}

    .slide-inner ul,
    .slide-inner ol {{
      font-size: 1.6em;
      color: #334155;
      line-height: 1.75;
      margin-bottom: 0.7em;
      padding-left: 1.5em;
    }}

    .slide-inner li {{
      margin-bottom: 0.3em;
    }}

    /* Nested lists: each level shrinks to 85% of its parent */
    .slide-inner li > ul,
    .slide-inner li > ol {{
      font-size: 0.85em;
      margin-bottom: 0;
    }}

    /* Loose lists wrap items in <p>; keep same size as the li, no double-scaling */
    .slide-inner li > p {{
      font-size: 1em;
      margin-bottom: 0.2em;
    }}

    .slide-inner a {{
      color: #2563eb;
      text-decoration: underline;
    }}

    .slide-inner strong {{
      color: #0f172a;
      font-weight: 600;
    }}

    .slide-inner em {{
      color: #475569;
    }}

    /* ── Code ── */
    .slide-inner code {{
      font-family: 'Cascadia Code', 'Fira Code', Consolas, 'Courier New', monospace;
      font-size: 0.88em;
      background: #e2e8f0;
      color: #475569;
      font-weight: 400;
      padding: 0.15em 0.45em;
      border-radius: 4px;
    }}

    .slide-inner pre {{
      background: #1e293b;
      color: #e2e8f0;
      border-radius: 8px;
      padding: 1.1em 1.4em;
      margin: 1em 0;
      overflow-x: auto;
      border: 1px solid #334155;
      box-shadow: 0 2px 12px rgba(0,0,0,0.12);
    }}

    .slide-inner pre code {{
      background: none;
      color: inherit;
      padding: 0;
      font-size: 1.3em;
      line-height: 1.65;
      border-radius: 0;
    }}

    /* ── Tables ── */
    .slide-inner table {{
      width: 100%;
      border-collapse: collapse;
      margin: 1em 0;
      font-size: 1.5em;
    }}

    .slide-inner th {{
      background: #1e40af;
      color: #fff;
      font-weight: 600;
      padding: 0.6em 1em;
      text-align: left;
    }}

    .slide-inner td {{
      padding: 0.55em 1em;
      color: #334155;
      border-bottom: 1px solid #e2e8f0;
    }}

    .slide-inner tr:nth-child(even) td {{
      background: #f1f5f9;
    }}

    /* ── Images ── */
    .slide-inner img {{
      max-width: 100%;
      max-height: 42vh;
      border-radius: 6px;
      display: block;
      margin: 0.8em auto;
      object-fit: contain;
    }}

    /* Mermaid diagram images: no shadow, no radius, no height cap */
    .slide-inner .mermaid-rendered img {{
      box-shadow: none;
      border-radius: 0;
      max-height: none;
      margin: 0 auto;
    }}

    /* Paragraph containing only images → side-by-side flex row */
    .slide-inner p:has(img):not(:has(*:not(img))) {{
      display: flex;
      flex-wrap: wrap;
      gap: 1.5em;
      justify-content: center;
      align-items: flex-start;
      margin-bottom: 0.8em;
    }}

    .slide-inner p:has(img):not(:has(*:not(img))) img {{
      flex: 1;
      min-width: 0;
      max-height: 38vh;
      margin: 0;
    }}

    /* ── Blockquote ── */
    .slide-inner blockquote {{
      border-left: 4px solid #3b82f6;
      background: #eff6ff;
      padding: 0.7em 1.2em;
      margin: 1em 0;
      border-radius: 0 6px 6px 0;
    }}

    .slide-inner blockquote p {{
      margin: 0;
      color: #1e40af;
      font-style: italic;
    }}

    /* ── Callout boxes ── */
    .slide-inner .callout {{
      border-left: 4px solid var(--callout-color, #3b82f6);
      background: var(--callout-bg, #eff6ff);
      border-radius: 0 8px 8px 0;
      margin: 1em 0;
      overflow: hidden;
    }}

    .slide-inner .callout-title {{
      font-size: 1.6em;
      font-weight: 700;
      color: var(--callout-color, #3b82f6);
      padding: 0.45em 0.75em;
      border-bottom: 1px solid color-mix(in srgb, var(--callout-color, #3b82f6) 20%, transparent);
      line-height: 1.4;
    }}

    .slide-inner .callout-body {{
      padding: 0.5em 0.75em 0.6em;
    }}

    .slide-inner .callout-body p {{
      font-size: 1.6em;
      margin-bottom: 0.4em;
      color: #334155;
    }}

    .slide-inner .callout-body p:last-child {{
      margin-bottom: 0;
    }}

    .slide-inner .callout-body ul,
    .slide-inner .callout-body ol {{
      font-size: 1.6em;
      margin-bottom: 0.4em;
    }}

    /* ── Highlights ==text== ── */
    .slide-inner mark {{
      background: #fef08a;
      color: #713f12;
      padding: 0.05em 0.25em;
      border-radius: 3px;
    }}

    /* ── Task lists ── */
    .slide-inner .task-list-item {{
      list-style: none;
    }}

    /* Top-level task list: no indent */
    .slide-inner ul:has(> .task-list-item) {{
      padding-left: 0;
    }}

    /* Nested task list: restore indent */
    .slide-inner li > ul:has(> .task-list-item) {{
      padding-left: 1.5em;
    }}

    .slide-inner .task-list-item input[type="checkbox"] {{
      margin-right: 0.5em;
      accent-color: #3b82f6;
      width: 1em;
      height: 1em;
      cursor: default;
    }}

    /* ── KaTeX math ── */
    /* Inline math: inherits 1.6em from <p>, no extra scaling needed */
    .slide-inner .math-inline .katex {{
      font-size: 1em;
    }}

    /* Display math: direct child of slide-inner, needs explicit size */
    .slide-inner .math-display {{
      font-size: 1.6em;
      margin: 0.8em 0;
      overflow-x: auto;
      text-align: center;
    }}

    /* ── Mermaid diagrams ── */
    /* Client-side fallback: keep a subtle frame since the SVG renders inline */
    .slide-inner .mermaid {{
      margin: 1em 0;
      text-align: center;
    }}
    .slide-inner .mermaid svg {{
      max-width: 100%;
      height: auto;
    }}

    /* Server-rendered: SVG is a self-contained <img>; no extra frame needed */
    .slide-inner .mermaid-rendered {{
      margin: 1em 0;
      text-align: center;
    }}
    .slide-inner .mermaid-rendered img {{
      max-width: 100%;
      height: auto;
      display: block;
      margin: 0 auto;
    }}

    /* ── Title slide (first slide) ── */
    .slide-title {{
      background: #ffffff;
    }}

    .slide-title .slide-inner {{
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      text-align: center;
      padding: 6% 12%;
      height: 100%;
    }}

    .slide-title .slide-inner h1 {{
      font-size: 5.5em;
      font-weight: 800;
      color: #0f172a;
      letter-spacing: -0.03em;
      line-height: 1.15;
      border-bottom: none;
      margin-bottom: 0.6em;
      padding-bottom: 0;
    }}

    /* Decorative line under title */
    .slide-title .slide-inner h1::after {{
      content: "";
      display: block;
      margin: 0.4em auto 0;
      width: 3em;
      height: 4px;
      border-radius: 2px;
      background: linear-gradient(90deg, #3b82f6, #06b6d4, #8b5cf6);
    }}

    .slide-title .slide-inner p,
    .slide-title .slide-inner li {{
      font-size: 2em;
      color: #475569;
      line-height: 1.7;
      margin-bottom: 0.4em;
    }}

    .slide-title .slide-inner ul,
    .slide-title .slide-inner ol {{
      list-style: none;
      padding: 0;
    }}

    .slide-title .slide-inner h2,
    .slide-title .slide-inner h3 {{
      font-size: 2em;
      font-weight: 500;
      color: #64748b;
      margin-top: 0.4em;
      margin-bottom: 0.3em;
    }}

    /* ── Navigation buttons ── */
    .nav-btn {{
      position: absolute;
      top: 50%;
      transform: translateY(-50%);
      width: clamp(32px, 4vw, 52px);
      height: clamp(32px, 4vw, 52px);
      border-radius: 50%;
      border: none;
      background: rgba(15, 23, 42, 0.55);
      color: #fff;
      font-size: clamp(1rem, 2.5vw, 1.6rem);
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      transition: background 0.2s, transform 0.15s, opacity 0.6s;
      z-index: 10;
      backdrop-filter: blur(4px);
      line-height: 1;
    }}

    .nav-btn:hover {{
      background: rgba(59, 130, 246, 0.8);
      transform: translateY(-50%) scale(1.08);
    }}

    .nav-btn:active {{
      transform: translateY(-50%) scale(0.96);
    }}

    .nav-btn.disabled {{
      opacity: 0.25;
      cursor: default;
      pointer-events: none;
    }}

    #btn-prev {{ left: 1.2%; }}
    #btn-next {{ right: 1.2%; }}

    /* ── Slide counter ── */
    #counter {{
      position: absolute;
      bottom: 1.8%;
      left: 50%;
      transform: translateX(-50%);
      font-size: clamp(0.65rem, 1.2vw, 0.85rem);
      color: #94a3b8;
      background: rgba(15, 23, 42, 0.06);
      padding: 0.25em 0.9em;
      border-radius: 20px;
      backdrop-filter: blur(4px);
      border: 1px solid rgba(15, 23, 42, 0.1);
      letter-spacing: 0.05em;
      user-select: none;
      z-index: 10;
    }}

    /* ── Progress bar ── */
    #progress-bar {{
      position: absolute;
      bottom: 0;
      left: 0;
      height: 3px;
      background: linear-gradient(90deg, #3b82f6, #06b6d4);
      transition: width 0.35s ease;
      z-index: 10;
    }}

    /* ── Top-right cluster ── */
    #top-right {{
      position: absolute;
      top: 1.6em;
      right: 1.6em;
      display: flex;
      align-items: center;
      gap: 5px;
      z-index: 20;
    }}

    /* Shared icon button style */
    .icon-btn {{
      width: clamp(20px, 2.2vw, 30px);
      height: clamp(20px, 2.2vw, 30px);
      border-radius: 6px;
      border: none;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      transition: background 0.2s, transform 0.15s;
      backdrop-filter: blur(4px);
      padding: 0;
      flex-shrink: 0;
    }}
    .icon-btn:hover {{ transform: scale(1.1); }}
    .icon-btn svg {{
      width: 55%;
      height: 55%;
      fill: none;
      stroke: #fff;
      stroke-width: 2;
      stroke-linecap: round;
      stroke-linejoin: round;
    }}

    /* ── Fullscreen button ── */
    #btn-fullscreen {{
      background: rgba(15, 23, 42, 0.5);
    }}
    #btn-fullscreen:hover {{ background: rgba(59, 130, 246, 0.85); }}

    /* ── TOC button ── */
    #btn-toc {{
      background: rgba(15, 23, 42, 0.5);
    }}
    #btn-toc:hover {{ background: rgba(59, 130, 246, 0.85); }}
    #btn-toc.toc-on {{ background: rgba(59, 130, 246, 0.85); }}

    /* ── TOC panel ── */
    #toc-panel {{
      display: none;
      position: absolute;
      top: calc(1.6em + clamp(20px, 2.2vw, 30px) + 8px);
      right: 1.6em;
      width: clamp(160px, 26%, 280px);
      max-height: 65%;
      overflow-y: auto;
      background: rgba(10, 18, 36, 0.92);
      border-radius: 8px;
      border: 1px solid rgba(255,255,255,0.1);
      backdrop-filter: blur(10px);
      z-index: 30;
      flex-direction: column;
      padding: 5px 0;
      scrollbar-width: thin;
      scrollbar-color: rgba(255,255,255,0.2) transparent;
    }}
    .toc-item {{
      display: flex;
      align-items: center;
      gap: 0.6em;
      padding: 0.45em 1em;
      color: rgba(255,255,255,0.7);
      cursor: pointer;
      font-size: clamp(0.65rem, 1.4vw, 1rem);
      transition: background 0.15s, color 0.15s;
    }}
    .toc-item:hover {{ background: rgba(255,255,255,0.1); color: #fff; }}
    .toc-item.toc-active {{ background: rgba(59,130,246,0.35); color: #fff; }}
    .toc-num {{
      opacity: 0.45;
      font-size: 0.85em;
      min-width: 1.4em;
      flex-shrink: 0;
    }}

    /* ── Author label ── */
    .ppt-author {{
      font-size: clamp(0.7rem, 1.1vw, 0.88rem);
      color: rgba(148, 163, 184, 0.75);
      white-space: nowrap;
      pointer-events: none;
    }}
    .ppt-author-sep {{
      display: inline-block;
      width: 1px;
      height: 1.2em;
      background: rgba(148, 163, 184, 0.35);
      margin: 0 4px;
      vertical-align: middle;
    }}

    /* ── Timer ── */
    #btn-timer-start {{
      background: rgba(15, 23, 42, 0.5);
    }}
    #btn-timer-start:hover {{ background: rgba(59, 130, 246, 0.85); }}

    #timer-running {{
      display: none;
      align-items: center;
      gap: 3px;
      background: rgba(37, 99, 235, 0.85);
      border-radius: 6px;
      padding: 0 6px;
      height: clamp(20px, 2.2vw, 30px);
      backdrop-filter: blur(4px);
    }}

    #timer-display {{
      font-size: clamp(0.5rem, 1.1vw, 0.75rem);
      font-family: 'Cascadia Code', 'Fira Code', Consolas, monospace;
      color: #fff;
      letter-spacing: 0.04em;
      min-width: 3em;
      text-align: center;
      flex-shrink: 0;
    }}

    .tbtn {{
      border: none;
      background: rgba(255,255,255,0.2);
      color: #fff;
      cursor: pointer;
      padding: 2px 5px;
      border-radius: 4px;
      font-size: clamp(0.5rem, 1.05vw, 0.72rem);
      line-height: 1;
      transition: background 0.15s;
    }}
    .tbtn:hover {{ background: rgba(255,255,255,0.4); }}

    /* ── Dark mode toggle button ── */
    #btn-dark {{ background: rgba(15, 23, 42, 0.5); }}
    #btn-dark:hover {{ background: rgba(59, 130, 246, 0.85); }}

    /* ── Dark mode ── */
    #stage.dark .slide,
    #stage.dark .slide-header {{
      background: linear-gradient(160deg, #0f172a 0%, #1a2e4a 100%);
    }}

    /* Dual-theme Mermaid: show light diagram normally, dark diagram in dark mode */
    .mermaid-rendered .diagram-light {{ display: block; }}
    .mermaid-rendered .diagram-dark  {{ display: none !important; }}
    #stage.dark .mermaid-rendered .diagram-light {{ display: none !important; }}
    #stage.dark .mermaid-rendered .diagram-dark  {{ display: block !important; }}

    #stage.dark .slide-header h1 {{
      color: #d8e8f7;
      border-bottom-color: #22395a;
    }}

    #stage.dark .slide-inner h1 {{
      color: #d8e8f7;
      border-bottom-color: #22395a;
    }}
    #stage.dark .slide-inner h2 {{ color: #6aacdf; }}
    #stage.dark .slide-inner h3 {{ color: #7a9bb4; }}

    #stage.dark .slide-inner p,
    #stage.dark .slide-inner ul,
    #stage.dark .slide-inner ol {{ color: #a8c2d6; }}

    #stage.dark .slide-inner strong {{ color: #dceaf7; }}
    #stage.dark .slide-inner em     {{ color: #6b8fa6; }}
    #stage.dark .slide-inner a      {{ color: #6aacdf; }}

    #stage.dark .slide-inner code {{
      background: #142030;
      color: #82bef0;
    }}
    #stage.dark .slide-inner pre {{
      background: #080e1a;
      border-color: #1c3350;
    }}
    #stage.dark .slide-inner pre code {{
      background: none;
      color: #b8d8f0;
    }}

    #stage.dark .slide-inner th {{
      background: #163166;
    }}
    #stage.dark .slide-inner td {{
      color: #a8c2d6;
      border-bottom-color: #1c3350;
    }}
    #stage.dark .slide-inner tr:nth-child(even) td {{
      background: #111e2f;
    }}

    #stage.dark .slide-inner blockquote {{
      background: rgba(30, 80, 160, 0.18);
      border-left-color: #4a8fc4;
    }}
    #stage.dark .slide-inner blockquote p {{
      color: #82bef0;
    }}

    #stage.dark .slide-title {{ background: linear-gradient(160deg, #0f172a 0%, #1a2e4a 100%); }}
    #stage.dark .slide-title .slide-inner h1    {{ color: #d8e8f7; }}
    #stage.dark .slide-title .slide-inner p,
    #stage.dark .slide-title .slide-inner li    {{ color: #7a9bb4; }}
    #stage.dark .slide-title .slide-inner h2,
    #stage.dark .slide-title .slide-inner h3    {{ color: #4e7a96; }}

    #stage.dark #counter {{
      color: #3d5a72;
      background: rgba(255,255,255,0.04);
      border-color: rgba(255,255,255,0.07);
    }}
    #stage.dark .slide-inner {{
      scrollbar-color: #22395a transparent;
    }}

    /* ── Dark mode: KaTeX math ── */
    #stage.dark .slide-inner .katex {{
      color: #a8c2d6;
    }}
    /* ── Pygments syntax highlighting ── */
    .slide-inner pre code.highlight {{
      display: block;
      background: none;
      color: inherit;
      padding: 0;
      font-size: 1.3em;
      line-height: 1.65;
    }}
    {highlight_css}
  </style>
</head>
<body>
  <div id="stage">
    <!-- Slides -->
{slides_html}
    <!-- Navigation -->
    <button id="btn-prev" class="nav-btn" onclick="changeSlide(-1)" title="上一页">&#8249;</button>
    <button id="btn-next" class="nav-btn" onclick="changeSlide(1)" title="下一页">&#8250;</button>

    <!-- Counter -->
    <div id="counter">
      <span id="cur">1</span>&nbsp;/&nbsp;<span id="tot">{total}</span>
    </div>

    <!-- Top-right cluster -->
    <div id="top-right">
      {author_html}
      <!-- Timer -->
      <button id="btn-timer-start" class="icon-btn" onclick="timerStart()" title="开始计时 (t)">
        <svg viewBox="0 0 24 24">
          <circle cx="12" cy="12" r="9"/>
          <polyline points="12 7 12 12 15 15"/>
        </svg>
      </button>
      <div id="timer-running">
        <span id="timer-display">00:00</span>
        <button class="tbtn" id="btn-timer-pause" onclick="timerPause()" title="暂停 (p)">⏸</button>
        <button class="tbtn" onclick="timerReset()" title="重置 (r)">↺</button>
        <button class="tbtn" onclick="timerStop()" title="停止 (t)">✕</button>
      </div>
      <!-- TOC -->
      <button id="btn-toc" class="icon-btn" onclick="toggleToc()" title="目录">
        <svg viewBox="0 0 24 24">
          <line x1="3" y1="6" x2="21" y2="6"/>
          <line x1="3" y1="12" x2="21" y2="12"/>
          <line x1="3" y1="18" x2="21" y2="18"/>
        </svg>
      </button>
      <!-- Dark mode -->
      <button id="btn-dark" class="icon-btn" onclick="toggleDark()" title="深色模式 (m)">
        <svg id="icon-sun" viewBox="0 0 24 24">
          <circle cx="12" cy="12" r="5"/>
          <line x1="12" y1="1" x2="12" y2="3"/>
          <line x1="12" y1="21" x2="12" y2="23"/>
          <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/>
          <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>
          <line x1="1" y1="12" x2="3" y2="12"/>
          <line x1="21" y1="12" x2="23" y2="12"/>
          <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/>
          <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
        </svg>
        <svg id="icon-moon" viewBox="0 0 24 24" style="display:none">
          <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
        </svg>
      </button>
      <!-- Fullscreen -->
      <button id="btn-fullscreen" class="icon-btn" onclick="toggleFullscreen()" title="全屏 (f)">
        <svg id="icon-expand" viewBox="0 0 24 24">
          <polyline points="15 3 21 3 21 9"/>
          <polyline points="9 21 3 21 3 15"/>
          <line x1="21" y1="3" x2="14" y2="10"/>
          <line x1="3" y1="21" x2="10" y2="14"/>
        </svg>
        <svg id="icon-compress" viewBox="0 0 24 24" style="display:none">
          <polyline points="4 14 10 14 10 20"/>
          <polyline points="20 10 14 10 14 4"/>
          <line x1="10" y1="14" x2="3" y2="21"/>
          <line x1="21" y1="3" x2="14" y2="10"/>
        </svg>
      </button>
    </div>

    <!-- TOC panel -->
    <div id="toc-panel"></div>

    <!-- Progress bar -->
    <div id="progress-bar"></div>
  </div>

  <script>
    const slides = document.querySelectorAll('.slide');
    const total = slides.length;
    let current = 0;
    let animating = false;
    const DURATION = 420;

    function updateUI() {{
      document.getElementById('cur').textContent = current + 1;
      document.getElementById('progress-bar').style.width =
        ((current + 1) / total * 100) + '%';
      document.getElementById('btn-prev').classList.toggle('disabled', current === 0);
      document.getElementById('btn-next').classList.toggle('disabled', current === total - 1);
      sessionStorage.setItem('slide', current);
    }}

    function goTo(n) {{
      if (n < 0 || n >= total || n === current || animating) return;
      animating = true;
      const dir = n > current ? 1 : -1;
      const oldSlide = slides[current];
      const newSlide = slides[n];

      // Snap new slide to entry position without transition
      newSlide.style.transition = 'none';
      newSlide.style.transform = `translateX(${{dir * 100}}%)`;
      newSlide.querySelector('.slide-inner').scrollTop = 0;

      // Force reflow so the snap takes effect before re-enabling transition
      newSlide.offsetHeight;

      // Animate both slides
      newSlide.style.transition = '';
      newSlide.style.transform = 'translateX(0)';
      newSlide.classList.add('active');

      oldSlide.style.transform = `translateX(${{-dir * 100}}%)`;

      setTimeout(() => {{
        oldSlide.classList.remove('active');
        oldSlide.style.transform = '';
        current = n;
        animating = false;
        updateUI();
        startCursorTimer();
      }}, DURATION);
    }}

    function changeSlide(dir) {{
      goTo(current + dir);
    }}

    // Fullscreen
    function toggleFullscreen() {{
      if (!document.fullscreenElement) {{
        document.documentElement.requestFullscreen();
      }} else {{
        document.exitFullscreen();
      }}
    }}

    document.addEventListener('fullscreenchange', () => {{
      const isFs = !!document.fullscreenElement;
      document.getElementById('icon-expand').style.display = isFs ? 'none' : '';
      document.getElementById('icon-compress').style.display = isFs ? '' : 'none';
      if (isFs) {{
        // Entered fullscreen: hide cursor immediately, reset lock
        stage.style.cursor = 'none';
        cursorHidden = true;
        cursorLocked = false;
        // Ignore mousemove for 2s to avoid browser's "Press Esc" banner triggering restore
        ignoreMouse = true;
        setTimeout(() => {{ ignoreMouse = false; }}, 2000);
      }} else {{
        // Exited fullscreen: always show cursor
        showCursorAndNav();
        cursorLocked = true;
      }}
    }});

    document.addEventListener('keydown', (e) => {{
      // Ignore shortcuts when modifier keys are held (Ctrl/Alt/Meta combos)
      if (e.ctrlKey || e.altKey || e.metaKey) return;
      // Ignore shortcuts when focus is inside an input/textarea
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
      switch (e.key) {{
        case 'ArrowRight': case 'PageDown':
          changeSlide(1); break;
        case 'ArrowLeft': case 'PageUp':
          changeSlide(-1); break;
        case 'ArrowDown': case 'ArrowUp': {{
          const inner = slides[current].querySelector('.slide-inner');
          if (inner) inner.scrollBy({{ top: e.key === 'ArrowDown' ? 80 : -80, behavior: 'smooth' }});
          break;
        }}
        case 'Home': goTo(0); break;
        case 'End':  goTo(total - 1); break;
        case ' ':
          e.preventDefault();
          changeSlide(1); break;
        case 'f': case 'F':
          toggleFullscreen(); break;
        case 't': case 'T':
          if (timerTick === null) timerStart(); else timerStop(); break;
        case 'p': case 'P':
          if (timerTick !== null) timerPause(); break;
        case 'r': case 'R':
          if (timerTick !== null) timerReset(); break;
        case 'c': case 'C':
          toggleToc(); break;
        case 'm': case 'M':
          toggleDark(); break;
        case 'Escape':
          closeToc(); break;
        default:
          if (e.key >= '0' && e.key <= '9') {{
            const n = parseInt(e.key);
            if (n < total) {{ goTo(n); closeToc(); }}
          }}
      }}
    }});

    // ── Cursor & nav fade ─────────────────────────────────────────────────
    const stage     = document.getElementById('stage');
    const btnPrev   = document.getElementById('btn-prev');
    const btnNext   = document.getElementById('btn-next');
    let cursorTimer   = null;

    // ── Dark mode ──────────────────────────────────────────────────────────
    let darkMode = localStorage.getItem('ppt-dark') === '1';
    function applyDark() {{
      stage.classList.toggle('dark', darkMode);
      document.getElementById('icon-sun').style.display  = darkMode ? 'none' : '';
      document.getElementById('icon-moon').style.display = darkMode ? ''     : 'none';
    }}
    function toggleDark() {{
      darkMode = !darkMode;
      localStorage.setItem('ppt-dark', darkMode ? '1' : '');
      applyDark();
    }}
    applyDark();
    let cursorHidden  = false;
    let cursorLocked  = false;   // once user moves mouse, don't re-hide until next slide change
    let ignoreMouse   = false;   // briefly ignore mousemove after entering fullscreen

    function hideNav() {{
      if (cursorLocked) return;
      btnPrev.style.opacity = '0.15';
      btnNext.style.opacity = '0.15';
    }}

    function showCursorAndNav() {{
      stage.style.cursor = '';
      btnPrev.style.opacity = '';
      btnNext.style.opacity = '';
      cursorHidden = false;
    }}

    function startCursorTimer() {{
      clearTimeout(cursorTimer);
      cursorLocked = false;
      showCursorAndNav();
      // Hide cursor immediately only when already in fullscreen
      if (document.fullscreenElement) {{
        stage.style.cursor = 'none';
        cursorHidden = true;
      }}
      // Fade nav buttons after 3s
      cursorTimer = setTimeout(hideNav, 3000);
    }}

    stage.addEventListener('mousemove', () => {{
      if (ignoreMouse) return;
      if (cursorHidden || !cursorLocked) {{
        showCursorAndNav();
        cursorLocked = true;
        clearTimeout(cursorTimer);
      }}
    }});

    // ── TOC ────────────────────────────────────────────────────────────────
    const tocPanel = document.getElementById('toc-panel');
    let tocOpen = false;

    function toggleToc() {{
      tocOpen ? closeToc() : openToc();
    }}

    function openToc() {{
      tocPanel.innerHTML = '';
      slides.forEach((slide, i) => {{
        const h1 = slide.querySelector('h1');
        const title = h1 ? h1.textContent.trim() : ('幻灯片 ' + (i + 1));
        const item = document.createElement('div');
        item.className = 'toc-item' + (i === current ? ' toc-active' : '');
        item.innerHTML = `<span class="toc-num">${{i}}</span><span>${{title}}</span>`;
        item.addEventListener('click', () => {{ goTo(i); closeToc(); }});
        tocPanel.appendChild(item);
      }});
      tocPanel.style.display = 'flex';
      tocOpen = true;
      document.getElementById('btn-toc').classList.add('toc-on');
    }}

    function closeToc() {{
      tocPanel.style.display = 'none';
      tocOpen = false;
      document.getElementById('btn-toc').classList.remove('toc-on');
    }}

    // Close TOC when clicking outside
    document.getElementById('btn-toc').addEventListener('click', e => e.stopPropagation());
    document.getElementById('stage').addEventListener('click', e => {{
      if (tocOpen && !tocPanel.contains(e.target)) closeToc();
    }});

    // ── Timer ──────────────────────────────────────────────────────────────
    let timerSecs = 0, timerTick = null, timerPaused = false;

    function timerFmt(s) {{
      const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), ss = s % 60;
      const p = n => String(n).padStart(2, '0');
      return h > 0 ? `${{p(h)}}:${{p(m)}}:${{p(ss)}}` : `${{p(m)}}:${{p(ss)}}`;
    }}

    function timerStart() {{
      document.getElementById('btn-timer-start').style.display = 'none';
      document.getElementById('timer-running').style.display = 'flex';
      timerPaused = false;
      timerTick = setInterval(() => {{
        if (!timerPaused) {{
          timerSecs++;
          document.getElementById('timer-display').textContent = timerFmt(timerSecs);
        }}
      }}, 1000);
    }}

    function timerPause() {{
      timerPaused = !timerPaused;
      const btn = document.getElementById('btn-timer-pause');
      btn.textContent = timerPaused ? '▶' : '⏸';
      btn.title = timerPaused ? '继续' : '暂停';
    }}

    function timerReset() {{
      timerSecs = 0;
      timerPaused = false;
      document.getElementById('btn-timer-pause').textContent = '⏸';
      document.getElementById('btn-timer-pause').title = '暂停';
      document.getElementById('timer-display').textContent = timerFmt(0);
    }}

    function timerStop() {{
      clearInterval(timerTick);
      timerTick = null; timerSecs = 0; timerPaused = false;
      document.getElementById('timer-running').style.display = 'none';
      document.getElementById('btn-timer-start').style.display = 'flex';
      document.getElementById('btn-timer-pause').textContent = '⏸';
      document.getElementById('btn-timer-pause').title = '暂停';
      document.getElementById('timer-display').textContent = timerFmt(0);
    }}

    // Initialise cursor timer on load
    startCursorTimer();

    // Initialise — restore last slide from sessionStorage
    const _saved = parseInt(sessionStorage.getItem('slide') || '0', 10);
    if (_saved > 0 && _saved < total) {{
      slides[_saved].classList.add('active');
      slides[0].classList.remove('active');
      current = _saved;
    }}
    updateUI();
  </script>

  <!-- KaTeX for LaTeX math rendering -->
  <script defer src="https://cdn.jsdelivr.net/npm/katex@0.16/dist/katex.min.js"
    onload="
      document.querySelectorAll('.math-display').forEach(el => {{
        katex.render(el.dataset.math, el, {{ displayMode: true, throwOnError: false }});
      }});
      document.querySelectorAll('.math-inline').forEach(el => {{
        katex.render(el.dataset.math, el, {{ displayMode: false, throwOnError: false }});
      }});
    "></script>

{mermaid_script_block}
</body>
</html>
"""
