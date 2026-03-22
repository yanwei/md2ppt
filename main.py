import sys
import os
import io

# Ensure stdout/stderr use UTF-8 on Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from md2ppt.parser import parse_slides
from md2ppt.generator import generate_html


def main():
    args = sys.argv[1:]

    if len(args) < 1:
        print("Usage: md2ppt <input.md> [output.html]")
        print("Example: md2ppt slides.md presentation.html")
        sys.exit(1)

    input_path = args[0]
    if not os.path.isfile(input_path):
        print(f"Error: file not found '{input_path}'")
        sys.exit(1)

    # Default output filename: replace extension with .html
    if len(args) >= 2:
        output_path = args[1]
    else:
        base = os.path.splitext(input_path)[0]
        output_path = base + ".html"

    # Use the filename (without extension) as the presentation title
    presentation_title = os.path.splitext(os.path.basename(input_path))[0]

    with open(input_path, encoding="utf-8") as f:
        md_text = f.read()

    slides = parse_slides(md_text)

    if not slides:
        print("Error: no slides found. Make sure the Markdown file has at least one '# ' heading.")
        sys.exit(1)

    html = generate_html(slides, title=presentation_title)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"[OK] Generated {len(slides)} slides -> {output_path}")


if __name__ == "__main__":
    main()
