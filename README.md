# md2ppt

Convert Markdown files into PPT-style static HTML presentations with a Python-only toolchain.

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
- **Mermaid diagrams** — fenced ` ```mermaid ` blocks rendered server-side to SVG (light + dark themes)
- **Math support** — inline and block LaTeX via KaTeX
- **Callout blocks** — `> [!NOTE]` / `[!WARNING]` / `[!TIP]` / `[!IMPORTANT]` styled callouts
- **Task lists** — `- [ ]` / `- [x]` checkboxes rendered in-slide
- **Dark mode** — toggle between light and dark themes (press `m`)
- **Web UI** — live browser editor with real-time preview and slide regeneration
- **Pure Python toolchain** — no Node.js or frontend build step required

## Installation

Requires Python 3.13+. Uses [uv](https://github.com/astral-sh/uv) for dependency management.

### As a global CLI tool (recommended)

```bash
git clone https://github.com/yourname/md2ppt.git
cd md2ppt
uv tool install .

# Install Chromium for server-side Mermaid rendering
uv run playwright install chromium
```

After installation, `md2ppt` is available globally from any directory.

### For development / Web UI

```bash
git clone https://github.com/yourname/md2ppt.git
cd md2ppt
uv sync
```

Dependencies installed by `uv sync`:

| Package | Purpose |
|:--------|:--------|
| `mistune` | Markdown parsing |
| `pygments` | Syntax highlighting in code blocks |
| `flask` | Web UI server |
| `playwright` | Headless Chromium for Mermaid SVG rendering |

## Usage

### CLI

```bash
# Output to <input>.html in the same directory
md2ppt slides.md

# Specify output path
md2ppt slides.md output.html

# Convert and open in browser immediately
md2ppt --open slides.md

# Show version
md2ppt --version
```

### Web UI

```bash
uv run python web_app.py
```

Starts a local server on `http://127.0.0.1:5002` by default.

For local development with Flask debug mode:

```bash
uv run python web_app.py --debug
```

For server deployment:

```bash
uv run python web_app.py --host 0.0.0.0 --port 5002
```

Recommended production setup is to keep `--debug` off and run behind a real process manager / reverse proxy.

## Deployment Notes

- Default web binding is `127.0.0.1` for safer local use
- Flask debug mode is opt-in via `--debug` or `MD2PPT_DEBUG=1`
- Generated HTML is a single-file presentation shell, but KaTeX and Mermaid fallback assets are loaded from CDN
- Server-side Mermaid rendering also requires network access the first time Chromium fetches Mermaid from CDN
- Web uploads store resource files in a flat per-presentation directory, so resource basenames must be unique

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
| `> [!NOTE]` / `[!WARNING]` / `[!TIP]` / `[!IMPORTANT]` | Styled callout block |
| ` ```mermaid ` | Mermaid diagram rendered to SVG when Playwright/Chromium is available; otherwise rendered client-side |
| `$...$` / `$$...$$` | Inline / block math via KaTeX |
| `- [ ]` / `- [x]` | Task list with checkboxes |

## Navigation

| Action | Keys / Controls |
|:-------|:----------------|
| Next slide | `→` `↓` `PageDown` or right button |
| Previous slide | `←` `↑` `PageUp` or left button |
| First slide | `Home` |
| Last slide | `End` |
| Fullscreen | Button in top-right corner |
| Exit fullscreen | `Esc` |
| Toggle dark mode | `m` |

## Project Structure

```
md2ppt/
├── main.py                      # CLI entry point
├── web_app.py                   # Flask web UI
├── md2ppt/
│   ├── __init__.py              # Package version
│   ├── parser.py                # Split Markdown into slides by H1 heading
│   ├── generator.py             # Render slides to a self-contained HTML file
│   └── mermaid_renderer.py      # Server-side Mermaid → SVG via Playwright
├── example.md                   # Example presentation source
├── example.html                 # Pre-generated demo (open directly in browser)
└── pyproject.toml
```

## License

MIT
