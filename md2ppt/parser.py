import re
import mistune
from pygments import highlight
from pygments.lexers import get_lexer_by_name
from pygments.lexers.special import TextLexer
from pygments.formatters import HtmlFormatter


# ── Callout type definitions ───────────────────────────────────────────────
_CALLOUT_TYPES: dict[str, tuple[str, str, str]] = {
    # key: (icon, border-color, background-color)
    'note':      ('ℹ️',  '#3b82f6', '#eff6ff'),
    'info':      ('ℹ️',  '#3b82f6', '#eff6ff'),
    'tip':       ('💡', '#10b981', '#f0fdf4'),
    'hint':      ('💡', '#10b981', '#f0fdf4'),
    'important': ('🔑', '#8b5cf6', '#f5f3ff'),
    'warning':   ('⚠️',  '#f59e0b', '#fffbeb'),
    'caution':   ('⚠️',  '#f59e0b', '#fffbeb'),
    'danger':    ('🚨', '#ef4444', '#fef2f2'),
    'error':     ('🚨', '#ef4444', '#fef2f2'),
    'bug':       ('🐛', '#ef4444', '#fef2f2'),
    'success':   ('✅', '#10b981', '#f0fdf4'),
    'check':     ('✅', '#10b981', '#f0fdf4'),
    'done':      ('✅', '#10b981', '#f0fdf4'),
    'question':  ('❓', '#8b5cf6', '#f5f3ff'),
    'faq':       ('❓', '#8b5cf6', '#f5f3ff'),
    'help':      ('❓', '#8b5cf6', '#f5f3ff'),
    'quote':     ('💬', '#64748b', '#f8fafc'),
    'cite':      ('💬', '#64748b', '#f8fafc'),
    'abstract':  ('📋', '#06b6d4', '#f0f9ff'),
    'summary':   ('📋', '#06b6d4', '#f0f9ff'),
    'tldr':      ('📋', '#06b6d4', '#f0f9ff'),
    'example':   ('📌', '#8b5cf6', '#f5f3ff'),
}

# Matches a rendered blockquote whose first <p> starts with [!TYPE]
# Group 1: callout type  Group 2: optional title  Group 3: rest of first <p>  Group 4: remaining HTML
_CALLOUT_HTML_RE = re.compile(
    r'<blockquote>\s*\n<p>\[!(\w+)\]([ \t]*[^\n<]*)?\n?(.*?)</p>(.*?)</blockquote>',
    re.DOTALL,
)


class _HighlightRenderer(mistune.HTMLRenderer):
    """mistune renderer with Pygments syntax highlighting and Mermaid support."""

    def block_code(self, code, info=None, **attrs):
        if info:
            lang = info.strip().split()[0]
            # Mermaid diagrams — output a plain div; mermaid.js renders it client-side
            if lang == 'mermaid':
                return f'<div class="mermaid">{code}</div>\n'
            try:
                lexer = get_lexer_by_name(lang, stripall=True)
            except Exception:
                lexer = TextLexer()
        else:
            lexer = TextLexer()
        formatter = HtmlFormatter(nowrap=True, cssclass='highlight')
        highlighted = highlight(code, lexer, formatter)
        return f'<pre><code class="highlight">{highlighted}</code></pre>\n'


def get_highlight_css() -> str:
    """Return Pygments CSS for the 'one-dark' (or fallback) style, without background."""
    for style in ('one-dark', 'monokai', 'dracula', 'native'):
        try:
            return HtmlFormatter(style=style, cssclass='highlight', nobackground=True).get_style_defs()
        except Exception:
            continue
    return HtmlFormatter(cssclass='highlight', nobackground=True).get_style_defs()


def parse_slides(md_text: str) -> list[str]:
    """
    Split markdown by H1 headings (# Title) into a list of HTML strings.
    Correctly ignores # inside fenced code blocks (``` or ~~~).
    ## and ### remain as in-slide subheadings.
    Content before the first H1 is discarded.
    """
    raw_slides = _split_by_h1(md_text)

    md = mistune.create_markdown(
        renderer=_HighlightRenderer(escape=False),
        plugins=['table', 'strikethrough', 'url', 'task_lists', 'mark'],
    )

    def render(slide_text: str) -> str:
        html = md(_ensure_blank_lines(_protect_math(_obsidian_images(slide_text))))
        return _process_callouts(html)

    return [render(s) for s in raw_slides]


# ── Obsidian syntax helpers ────────────────────────────────────────────────

_OBSIDIAN_IMG_RE = re.compile(r'!\[\[([^\]|]+?)(?:\|[^\]]+?)?\]\]')


def _obsidian_images(text: str) -> str:
    """Convert Obsidian embed syntax ![[file.png]] to standard ![file.png](file.png)."""
    return _OBSIDIAN_IMG_RE.sub(lambda m: f'![{m.group(1)}]({m.group(1)})', text)


def _process_callouts(html: str) -> str:
    """Post-process rendered HTML: transform blockquotes with [!TYPE] into callout divs."""
    def replace(m: re.Match) -> str:
        ctype = m.group(1).lower()
        title = (m.group(2) or '').strip() or ctype.capitalize()
        first_p_rest = (m.group(3) or '').strip()
        rest = (m.group(4) or '').strip()

        icon, color, bg = _CALLOUT_TYPES.get(ctype, ('💡', '#3b82f6', '#eff6ff'))

        body_parts = []
        if first_p_rest:
            body_parts.append(f'<p>{first_p_rest}</p>')
        if rest:
            body_parts.append(rest)
        body = '\n'.join(body_parts)

        return (
            f'<div class="callout callout-{ctype}" '
            f'style="--callout-color:{color};--callout-bg:{bg}">'
            f'<div class="callout-title">{icon} {title}</div>'
            f'<div class="callout-body">{body}</div>'
            f'</div>'
        )

    return _CALLOUT_HTML_RE.sub(replace, html)


# ── Math protection ───────────────────────────────────────────────────────

# Block math: $$...$$ (multiline or single-line)
_BLOCK_MATH_RE = re.compile(r'\$\$\s*([\s\S]*?)\s*\$\$')
# Inline math: $...$ (not $$)
_INLINE_MATH_RE = re.compile(r'(?<!\$)\$([^\$\n]+?)\$(?!\$)')


def _protect_math(text: str) -> str:
    """
    Convert $...$ and $$...$$ to HTML placeholder elements with a data-math
    attribute so mistune never touches the LaTeX content.
    KaTeX renders these elements client-side.
    """
    import html as _html

    _CODE_FENCE_RE = re.compile(r'(```[\s\S]*?```|~~~[\s\S]*?~~~)', re.MULTILINE)
    parts = _CODE_FENCE_RE.split(text)
    result = []
    for i, part in enumerate(parts):
        if i % 2 == 1:          # inside fenced code block — leave untouched
            result.append(part)
            continue
        # Block math first (so $$ isn't eaten by inline pattern)
        def block_repl(m: re.Match) -> str:
            escaped = _html.escape(m.group(1).strip(), quote=True)
            return f'<div class="math-display" data-math="{escaped}"></div>'
        part = _BLOCK_MATH_RE.sub(block_repl, part)
        # Inline math
        def inline_repl(m: re.Match) -> str:
            escaped = _html.escape(m.group(1), quote=True)
            return f'<span class="math-inline" data-math="{escaped}"></span>'
        part = _INLINE_MATH_RE.sub(inline_repl, part)
        result.append(part)
    return ''.join(result)


# ── Markdown preprocessing ─────────────────────────────────────────────────

def _ensure_blank_lines(text: str) -> str:
    """
    Ensure block-level elements are preceded by a blank line.

    Rules:
    - Headings (## / ###): always require a blank line before them,
      even when the previous line is itself a block element (e.g. a blockquote).
    - Blockquotes (>) and horizontal rules: only need a blank line when
      transitioning from a non-block line, so consecutive > lines stay together.
    """
    heading_re = re.compile(r'^#{2,}\s')
    other_block_re = re.compile(r'^(>|-{3,}|={3,})')
    lines = text.splitlines()
    result = []
    for line in lines:
        prev = result[-1] if result else ''
        if prev.strip():
            if heading_re.match(line):
                # Headings always need a blank line before them
                result.append('')
            elif other_block_re.match(line) and not other_block_re.match(prev) and not heading_re.match(prev):
                # Other block elements only need a blank line on non-block transition
                result.append('')
        result.append(line)
    return '\n'.join(result)


def _split_by_h1(md_text: str) -> list[str]:
    """Line-by-line split on H1, skipping content inside fenced code blocks."""
    lines = md_text.splitlines()
    slides: list[list[str]] = []
    current: list[str] = []
    in_fence = False
    fence_marker = ""

    h1_pattern = re.compile(r'^# (?!#)')

    for line in lines:
        stripped = line.strip()

        # Track fenced code block boundaries (``` or ~~~)
        if not in_fence:
            if stripped.startswith('```') or stripped.startswith('~~~'):
                in_fence = True
                fence_marker = stripped[:3]
        else:
            if stripped.startswith(fence_marker):
                in_fence = False

        # Only treat as a slide boundary when outside a code block
        if not in_fence and h1_pattern.match(line):
            if current and any(h1_pattern.match(l) for l in current):
                slides.append(current)
            elif current:
                # content before first H1 — discard
                pass
            current = [line]
        else:
            current.append(line)

    if current and any(h1_pattern.match(l) for l in current):
        slides.append(current)

    return ['\n'.join(s) for s in slides]
