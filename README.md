# md2ppt

Convert Markdown files into PPT-style static HTML presentations — no build tools, no dependencies beyond Python.

## Demo

Open `example.html` in any modern browser to see a live demo.

## Features

- **Slide-per-heading** — each `#` H1 becomes one slide; `##` / `###` are in-slide subheadings
- **Cover slide** — the first slide is automatically styled as a centered title page
- **Fixed slide title** — the title and divider line stay pinned while long content scrolls
- **Keyboard navigation** — `←` / `→`, `PageUp` / `PageDown`, `Home` / `End`
- **On-screen buttons** — left/right navigation arrows + fullscreen toggle
- **Slide transition** — smooth left/right slide animation
- **Proportional font sizing** — all text scales with the slide (true 16:9 layout on any screen)
- **Rich Markdown support** — tables, fenced code blocks, images, blockquotes, inline code
- **Multi-image layout** — multiple images in the same paragraph are displayed side by side
- **Pure Python** — generates a single self-contained HTML file, no Node.js or frontend toolchain needed

## Installation

Requires Python 3.13+. Uses [uv](https://github.com/astral-sh/uv) for dependency management.

```bash
git clone https://github.com/yourname/md2ppt.git
cd md2ppt
uv sync
```

## Usage

```bash
# Output to <input>.html in the same directory
uv run python main.py slides.md

# Specify output path
uv run python main.py slides.md output.html
```

Then open the generated HTML file in any modern browser.

## Markdown Format

```markdown
# Cover Title

Subtitle or description text here.

# Slide Two

## Subheading

Regular paragraph content. Supports **bold**, *italic*, `inline code`, etc.

## Another Section

- Bullet point one
- Bullet point two

# Code Example

## Python

    ```python
    def hello():
        print("Hello, world!")
    ```

# Table Example

| Column A | Column B |
|:---------|:---------|
| Value 1  | Value 2  |

# Image Slide

Single image (centered):

![description](path/to/image.png)

Multiple images (side by side):

![one](img1.png)
![two](img2.png)
![three](img3.png)

# Thank You
```

### Rules

| Markdown element | Rendered as |
|:-----------------|:------------|
| `# Title` | New slide (H1 becomes slide title) |
| `## Subtitle` | In-slide subheading |
| `### Sub-subtitle` | In-slide smaller subheading |
| Code fences ` ``` ` | Dark-themed code block |
| `\| table \|` | Styled table with header |
| `![alt](url)` | Embedded image |
| Multiple `![...]` on consecutive lines | Side-by-side image row |
| `> blockquote` | Blue-accented quote block |

## Navigation

| Action | Keys / Controls |
|:-------|:----------------|
| Next slide | `→` `↓` `PageDown` or right button |
| Previous slide | `←` `↑` `PageUp` or left button |
| First slide | `Home` |
| Last slide | `End` |
| Fullscreen | Button in top-right corner |
| Exit fullscreen | `Esc` |

## Project Structure

```
md2ppt/
├── main.py              # CLI entry point
├── md2ppt/
│   ├── parser.py        # Split Markdown into slides by H1 heading
│   └── generator.py     # Render slides to a self-contained HTML file
├── example.md           # Example presentation
├── example.html         # Pre-generated demo (open directly in browser)
└── pyproject.toml
```

## License

MIT
