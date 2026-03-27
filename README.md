# md2ppt

Convert Markdown files into PPT-style static HTML presentations with a Python-only toolchain.

## Demo

Open `example.html` in any modern browser to see a live demo.

Online: https://openclaw.yanyifan.com/md2ppt/

## Features

- **Slide-per-heading** — each `#` H1 becomes one slide; `##` / `###` are in-slide subheadings
- **Cover slide** — the first slide is automatically styled as a centered title page
- **Fixed slide title** — the title and divider line stay pinned while long content scrolls
- **Keyboard navigation** — `←` / `→`, `PageUp` / `PageDown`, `Home` / `End`
- **On-screen buttons** — left/right navigation arrows + fullscreen toggle
- **Slide transition** — smooth left/right slide animation
- **Progress bar** — visual progress indicator at the bottom of each slide
- **Table of contents** — slide navigator panel (press `c`)
- **Proportional font sizing** — all text scales with the slide (true 16:9 layout on any screen)
- **Rich Markdown support** — tables, fenced code blocks, images, blockquotes, inline code
- **Multi-image layout** — multiple images in the same paragraph are displayed side by side
- **Mermaid diagrams** — fenced ` ```mermaid ` blocks rendered server-side to SVG (light + dark themes)
- **Math support** — inline and block LaTeX via KaTeX
- **Callout blocks** — `> [!NOTE]` / `[!WARNING]` / `[!TIP]` / `[!IMPORTANT]` styled callouts
- **Task lists** — `- [ ]` / `- [x]` checkboxes rendered in-slide
- **Dark mode** — toggle between light and dark themes (press `m`)
- **Presentation timer** — built-in countdown timer (press `t`)
- **Web UI** — browser-based editor with upload, preview, and record management
- **Username login** — simple username-based login (no password); same username restores previous records
- **Feishu login** — OAuth 2.0 login via Feishu QR code scan (optional, web UI only)
- **Record ownership** — each upload is tied to the logged-in user; private by default
- **Share / unshare** — make any of your presentations publicly accessible by URL
- **Author watermark** — "Created by \<name\>" shown in the top-right corner of the presentation
- **Pure Python toolchain** — no Node.js or frontend build step required

## Installation

Requires Python 3.13+. Uses [uv](https://github.com/astral-sh/uv) for dependency management.

### As a global CLI tool (recommended)

```bash
git clone https://github.com/yanwei/md2ppt.git
cd md2ppt
uv tool install .

# Install Chromium for server-side Mermaid rendering
uv run playwright install chromium
```

After installation, `md2ppt` is available globally from any directory.

### For development / Web UI

```bash
git clone https://github.com/yanwei/md2ppt.git
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
| `gunicorn` | Production WSGI server |
| `python-dotenv` | `.env` file support |

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

> **Note:** The CLI has no authentication, ownership, or visibility features. Those are web UI only.

### Web UI

```bash
uv run python web_app.py
```

Starts a local server on `http://127.0.0.1:5002` by default. Open `/login` to sign in with a username or (if configured) Feishu OAuth.

```bash
# Flask debug mode (auto-reload templates)
uv run python web_app.py --debug

# Bind to all interfaces (for server deployment)
uv run python web_app.py --host 0.0.0.0 --port 5002
```

## Environment Variables

Copy `.env.example` to `.env` and fill in the values:

```bash
cp .env.example .env
```

| Variable | Required | Description |
|:---------|:---------|:------------|
| `FEISHU_APP_ID` | Yes (for login) | Feishu app ID (`cli_xxx`) |
| `FEISHU_APP_SECRET` | Yes (for login) | Feishu app secret |
| `FEISHU_REDIRECT_URI` | Production only | OAuth callback URL (default: `http://127.0.0.1:5002/auth/callback`) |
| `MD2PPT_HOST` | No | Bind host (default: `127.0.0.1`) |
| `MD2PPT_PORT` | No | Bind port (default: `5002`) |
| `MD2PPT_DEBUG` | No | Enable debug mode (`true`/`false`) |

If `FEISHU_APP_ID` is not set, the web UI falls back to username-only login (enter any username; same username restores previous records).

## Feishu Login Setup

1. Go to [Feishu Open Platform](https://open.feishu.cn/app) and open your app
2. Navigate to **Security Settings → Redirect URLs**
3. Add your callback URL(s):
   - Local dev: `http://127.0.0.1:5002/auth/callback`
   - Production: `https://your-domain.com/md2ppt/auth/callback`
4. Fill in `.env` with your `FEISHU_APP_ID` and `FEISHU_APP_SECRET`

The app does not need to be published on Feishu — OAuth login works in the "pending release" state.

## Deployment

### Nginx + Gunicorn (subpath)

Nginx config example for serving at `/md2ppt/`:

```nginx
location ^~ /md2ppt {
    client_max_body_size 500m;
    proxy_pass http://127.0.0.1:5002/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

Set `FEISHU_REDIRECT_URI=https://your-domain.com/md2ppt/auth/callback` in the server's `.env`.

### Notes

- Default web binding is `127.0.0.1` for safer local use
- Flask debug mode is opt-in via `--debug` or `MD2PPT_DEBUG=true`
- Generated HTML is a single-file presentation shell; KaTeX and Mermaid fallback assets are loaded from CDN
- Server-side Mermaid rendering requires network access the first time Chromium fetches Mermaid from CDN
- Web uploads store resource files in a flat per-presentation directory; resource basenames must be unique
- The `data/` directory holds the SQLite database and all uploaded files — back this up for persistence

## Web UI — Record Management

Each uploaded presentation is shown as a card in the record list. The action button on each card is a **split button**:

- **Left (▶)** — open the presentation in a new tab
- **Right (˅)** — dropdown menu with:
  - **重新生成** — re-convert the original MD file (own records and unclaimed records only)
  - **设为公开 / 设为私有** — toggle visibility (own records only)
  - **下载原始 MD** — download the source Markdown file
  - **认领此记录** — claim an unclaimed (no-owner) record as your own; it becomes private
  - **删除记录** — delete the presentation and all its files (own records and unclaimed records only)

### Visibility rules

| Record type | Who can see | Who can edit/delete | Play URL |
|:------------|:------------|:--------------------|:---------|
| Own — private | Owner only | Owner | No auth required |
| Own — public | Everyone | Owner | No auth required |
| Unclaimed (no owner) | Everyone | Everyone | No auth required |
| Others' public | Everyone | Owner only | No auth required |

> Play URLs (`/play/<id>`) require no login — anyone with the link can view the presentation.

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
| `> [!NOTE]` / `[!WARNING]` / `[!TIP]` / `[!IMPORTANT]` | Styled callout block (also supports `[!CAUTION]`, `[!DANGER]`, `[!ERROR]`, `[!BUG]`, `[!SUCCESS]`, `[!QUESTION]`, `[!FAQ]`, `[!ABSTRACT]`, `[!EXAMPLE]`, `[!QUOTE]`, and more) |
| ` ```mermaid ` | Mermaid diagram rendered to SVG when Playwright/Chromium is available; otherwise rendered client-side |
| `$...$` / `$$...$$` | Inline / block math via KaTeX |
| `- [ ]` / `- [x]` | Task list with checkboxes |
| `==text==` | Highlighted (marked) text |
| `![[filename.png]]` | Obsidian-style image embed (converted to standard markdown) |

## Navigation

| Action | Keys / Controls |
|:-------|:----------------|
| Next slide | `→` `↓` `PageDown` `Space` or right button |
| Previous slide | `←` `↑` `PageUp` or left button |
| First slide | `Home` |
| Last slide | `End` |
| Jump to slide N | `0`–`9` |
| Scroll within slide | `↑` / `↓` (when not at slide boundary) |
| Fullscreen | `f` or button in top-right corner |
| Exit fullscreen | `Esc` |
| Toggle dark mode | `m` |
| Start / stop timer | `t` |
| Pause / resume timer | `p` |
| Reset timer | `r` |
| Toggle TOC | `c` |

## Project Structure

```
md2ppt/
├── main.py                      # CLI entry point
├── web_app.py                   # Flask web UI + auth
├── md2ppt/
│   ├── __init__.py              # Package version
│   ├── parser.py                # Split Markdown into slides by H1 heading
│   ├── generator.py             # Render slides to a self-contained HTML file
│   └── mermaid_renderer.py      # Server-side Mermaid → SVG via Playwright
├── templates/
│   ├── index.html               # Web UI main page
│   └── login.html               # Feishu login page
├── .env.example                 # Environment variable reference
├── example.md                   # Example presentation source
├── example.html                 # Pre-generated demo (open directly in browser)
└── pyproject.toml
```

## License

MIT
