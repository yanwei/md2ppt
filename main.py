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


def _find_file(base_dir: str, filename: str) -> str | None:
    """Search base_dir recursively for filename, returning absolute path if found."""
    for dirpath, dirnames, filenames in os.walk(base_dir):
        # prioritise attachments/ by sorting it first
        dirnames.sort(key=lambda d: (0 if d == 'attachments' else 1, d))
        if filename in filenames:
            return os.path.join(dirpath, filename)
    return None


def _embed_images(html: str, base_dir: str) -> str:
    """Replace relative img src paths with base64 data URIs."""
    def replace(m: re.Match) -> str:
        src = m.group(2)
        if src.startswith(('data:', 'http://', 'https://', '//')):
            return m.group(0)
        filename = os.path.basename(urllib.parse.unquote(src))
        filepath = _find_file(base_dir, filename)
        if filepath is None:
            return m.group(0)
        mime, _ = mimetypes.guess_type(filepath)
        mime = mime or 'image/png'
        with open(filepath, 'rb') as f:
            data = base64.b64encode(f.read()).decode('ascii')
        return f'{m.group(1)}data:{mime};base64,{data}{m.group(3)}'
    return _IMG_SRC_RE.sub(replace, html)


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
    html = _embed_images(html, os.path.dirname(os.path.abspath(input_path)))

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"[OK] Generated {len(slides)} slide(s) -> {output_path}")

    if open_after:
        import subprocess
        subprocess.run(['open', os.path.abspath(output_path)])


if __name__ == "__main__":
    main()
