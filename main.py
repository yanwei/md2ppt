import sys
import os
import io
import re
import base64
import mimetypes
import urllib.parse
from md2ppt import __version__

# Ensure stdout/stderr use UTF-8 on Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from md2ppt.parser import parse_slides
from md2ppt.generator import generate_html


USAGE = """\
Usage: md2ppt [--open] <input.md> [output.html]

Convert a Markdown file into a PPT-style HTML presentation.

Options:
  --open        Open the output file in the default browser after conversion
  --version     Show version number and exit

Arguments:
  input.md      Path to the source Markdown file
  output.html   Output file path (default: same name as input with .html)

Examples:
  md2ppt slides.md
  md2ppt --open slides.md
  md2ppt slides.md presentation.html\
"""


_IMG_SRC_RE = re.compile(r'(<img\s[^>]*src=")([^"]+)(")', re.IGNORECASE)

# How many parent levels above the input file's directory to probe for assets.
_MAX_ANCESTOR_LEVELS = 8
# Obsidian keeps every attachment in a single vault-level folder by default.
_ATTACHMENT_DIRNAME = 'attachments'
# Marker that identifies an Obsidian vault root.
_VAULT_MARKER = '.obsidian'
# (base_dir, filename) -> absolute path or None; avoids re-walking for repeated refs.
_FIND_CACHE: dict[tuple[str, str], str | None] = {}


def _walk_for_file(root: str, filename: str) -> str | None:
    """Recursively search root for filename, visiting attachments/ first."""
    for dirpath, dirnames, filenames in os.walk(root):
        # prioritise attachments/ by sorting it first
        dirnames.sort(key=lambda d: (0 if d == _ATTACHMENT_DIRNAME else 1, d))
        if filename in filenames:
            return os.path.join(dirpath, filename)
    return None


def _iter_ancestors(path: str, max_levels: int = _MAX_ANCESTOR_LEVELS):
    """Yield path, then each parent directory upwards (bounded by max_levels)."""
    current = os.path.abspath(path)
    for _ in range(max_levels):
        yield current
        parent = os.path.dirname(current)
        if parent == current:      # filesystem root reached
            return
        current = parent


def _find_file(base_dir: str, filename: str) -> str | None:
    """Locate filename, looking beyond base_dir when assets live elsewhere.

    Search order (first hit wins):
    1. base_dir/attachments/ and base_dir/ — direct stat, Obsidian flat layout
    2. base_dir recursively — the original behaviour, attachments/ first
    3. each ancestor directory: direct stat, then <ancestor>/attachments/
    4. the nearest ancestor holding .obsidian/ (vault root), recursively
    """
    base_abs = os.path.abspath(base_dir)
    cache_key = (base_abs, filename)
    if cache_key in _FIND_CACHE:
        return _FIND_CACHE[cache_key]

    result = _locate_file(base_abs, filename)
    _FIND_CACHE[cache_key] = result
    return result


def _locate_file(base_abs: str, filename: str) -> str | None:
    def _direct(directory: str) -> str | None:
        candidate = os.path.join(directory, filename)
        return candidate if os.path.isfile(candidate) else None

    # 1. flat hits directly inside base_dir / base_dir/attachments
    for directory in (os.path.join(base_abs, _ATTACHMENT_DIRNAME), base_abs):
        hit = _direct(directory)
        if hit:
            return hit

    # 2. original behaviour: recursive search below base_dir
    hit = _walk_for_file(base_abs, filename)
    if hit:
        return hit

    # 3. ancestors — assets often sit in a vault-level folder beside the note
    ancestors = list(_iter_ancestors(base_abs))[1:]     # skip base_abs itself
    for ancestor in ancestors:
        for directory in (os.path.join(ancestor, _ATTACHMENT_DIRNAME), ancestor):
            hit = _direct(directory)
            if hit:
                return hit

    # 4. last resort: recursively search the nearest Obsidian vault root
    for ancestor in ancestors:
        if os.path.isdir(os.path.join(ancestor, _VAULT_MARKER)):
            hit = _walk_for_file(ancestor, filename)
            if hit:
                return hit
            break

    return None


def _embed_images(html: str, base_dir: str) -> tuple[str, list[str]]:
    """Replace relative img src paths with base64 data URIs.

    Returns (html, missing) where missing lists the image references that
    could not be resolved on disk and were therefore left as relative paths.
    """
    missing: list[str] = []

    def replace(m: re.Match) -> str:
        src = m.group(2)
        if src.startswith(('data:', 'http://', 'https://', '//')):
            return m.group(0)
        filename = os.path.basename(urllib.parse.unquote(src))
        filepath = _find_file(base_dir, filename)
        if filepath is None:
            if filename not in missing:
                missing.append(filename)
            return m.group(0)
        mime, _ = mimetypes.guess_type(filepath)
        mime = mime or 'image/png'
        with open(filepath, 'rb') as f:
            data = base64.b64encode(f.read()).decode('ascii')
        return f'{m.group(1)}data:{mime};base64,{data}{m.group(3)}'

    return _IMG_SRC_RE.sub(replace, html), missing


def main():
    args = sys.argv[1:]

    if args and args[0] in ('-V', '--version'):
        print(f"md2ppt {__version__}")
        sys.exit(0)

    if len(args) < 1 or args[0] in ('-h', '--help'):
        print(USAGE)
        sys.exit(0 if args and args[0] in ('-h', '--help') else 1)

    open_after = '--open' in args
    args = [a for a in args if a != '--open']

    input_path = args[0]
    if not os.path.isfile(input_path):
        print(f"md2ppt: '{input_path}': No such file", file=sys.stderr)
        print(f"Try 'md2ppt --help' for more information.", file=sys.stderr)
        sys.exit(1)

    # Default output filename: replace extension with .html
    if len(args) >= 2:
        output_path = args[1]
    else:
        base = os.path.splitext(input_path)[0]
        output_path = base + ".html"

    # Use the filename (without extension) as the presentation title
    presentation_title = os.path.splitext(os.path.basename(input_path))[0]

    with open(input_path, encoding="utf-8-sig") as f:
        md_text = f.read()

    slides = parse_slides(md_text)
    html = generate_html(slides, title=presentation_title)
    html, missing_images = _embed_images(
        html, os.path.dirname(os.path.abspath(input_path))
    )

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"[OK] Generated {len(slides)} slide(s) -> {output_path}")

    if missing_images:
        print(
            f"[WARN] {len(missing_images)} image(s) not found on disk and left as "
            f"relative paths (they will not render):",
            file=sys.stderr,
        )
        for name in missing_images:
            print(f"       - {name}", file=sys.stderr)

    if open_after:
        import subprocess
        abs_path = os.path.abspath(output_path)
        if sys.platform == 'win32':
            os.startfile(abs_path)
        else:
            subprocess.run(['open', abs_path])


if __name__ == "__main__":
    main()
