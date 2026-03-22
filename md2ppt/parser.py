import re
import markdown


def parse_slides(md_text: str) -> list[str]:
    """
    Split markdown by H1 headings (# Title) into a list of HTML strings.
    Correctly ignores # inside fenced code blocks (``` or ~~~).
    ## and ### remain as in-slide subheadings.
    Content before the first H1 is discarded.
    """
    raw_slides = _split_by_h1(md_text)

    md = markdown.Markdown(extensions=['extra', 'fenced_code'])
    result = []
    for slide_text in raw_slides:
        md.reset()
        result.append(md.convert(slide_text))
    return result


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
