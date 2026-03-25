import os
import re
import uuid
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from flask import (
    Flask, request, jsonify, send_from_directory,
    render_template, Response, g, abort
)

from md2ppt.parser import parse_slides
from md2ppt.generator import generate_html
from md2ppt import __version__ as _APP_VERSION

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR  = Path(__file__).parent
DATA_DIR  = BASE_DIR / "data"
FILES_DIR = DATA_DIR / "files"
DB_PATH   = DATA_DIR / "md2ppt.db"

DATA_DIR.mkdir(exist_ok=True)
FILES_DIR.mkdir(exist_ok=True)

# ── Flask app ─────────────────────────────────────────────────────────────────
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 500 * 1024 * 1024   # 500 MB

# ── UUID validation ───────────────────────────────────────────────────────────
_UUID_RE = re.compile(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$',
    re.IGNORECASE,
)

def valid_uuid(s: str) -> bool:
    return bool(_UUID_RE.match(s))

def require_uuid(s: str) -> str:
    """Abort 400 if s is not a valid UUID v4, else return s."""
    if not valid_uuid(s):
        abort(400)
    return s

# ── Database ──────────────────────────────────────────────────────────────────
def get_db() -> sqlite3.Connection:
    if "db" not in g:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        g.db = conn
    return g.db


@app.teardown_appcontext
def close_db(_):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS presentations (
            id          TEXT    PRIMARY KEY,
            title       TEXT    NOT NULL,
            filename    TEXT    NOT NULL,
            resources   TEXT    NOT NULL DEFAULT '',
            upload_time TEXT    NOT NULL,
            md_size     INTEGER NOT NULL DEFAULT 0,
            slide_count INTEGER NOT NULL DEFAULT 0,
            status      TEXT    NOT NULL DEFAULT 'ok',
            error_msg   TEXT    NOT NULL DEFAULT ''
        )
    """)
    conn.commit()
    conn.close()


# ── Conversion helpers ────────────────────────────────────────────────────────
_H1_TEXT_RE = re.compile(r"<h1[^>]*>(.*?)</h1>", re.DOTALL)
_ASSET_RE   = re.compile(
    r'(src|href)=(["\'])(?!https?://|//|/|#|data:)([^"\']+)\2',
    re.IGNORECASE,
)


def _extract_title(slide_html: str, fallback: str) -> str:
    import html as _html
    m = _H1_TEXT_RE.search(slide_html)
    if not m:
        return fallback
    return _html.unescape(re.sub(r"<[^>]+>", "", m.group(1))).strip() or fallback


def _rewrite_assets(html: str, pres_id: str) -> str:
    """Replace relative src/href with just the basename.
    The generated HTML is served from /files/{uuid}/, so bare filenames
    resolve correctly regardless of the deployment subpath."""
    def replacer(m):
        attr, quote, path = m.group(1), m.group(2), m.group(3)
        # Handle both forward slash and backslash path separators
        basename = re.split(r'[/\\]', path)[-1]
        return f'{attr}={quote}{basename}{quote}'
    return _ASSET_RE.sub(replacer, html)


def convert(md_text: str, md_filename: str) -> dict:
    """Return dict with html, title, slide_count. Raises ValueError on failure."""
    slides = parse_slides(md_text)
    if not slides:
        raise ValueError("Markdown 中没有找到任何幻灯片（需要至少一个 # 一级标题）")
    fallback = os.path.splitext(md_filename)[0]
    title    = _extract_title(slides[0], fallback)
    html     = generate_html(slides, title=title)
    return {"html": html, "title": title, "slide_count": len(slides)}


# ── Routes ────────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html", version=_APP_VERSION)


@app.route("/example.md")
def download_example():
    return send_from_directory(BASE_DIR / "example", "example.md", as_attachment=True)


@app.route("/api/presentations")
def list_presentations():
    rows = get_db().execute(
        "SELECT * FROM presentations ORDER BY upload_time DESC"
    ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["resources"] = [x for x in d["resources"].split(",") if x]
        result.append(d)
    return jsonify(result)


@app.route("/api/check-filename")
def check_filename():
    name = request.args.get("name", "")
    row = get_db().execute(
        "SELECT id, title, upload_time FROM presentations "
        "WHERE filename = ? ORDER BY upload_time DESC LIMIT 1",
        (name,),
    ).fetchone()
    if row:
        return jsonify({"exists": True, "latest": dict(row)})
    return jsonify({"exists": False, "latest": None})


@app.route("/api/upload", methods=["POST"])
def upload():
    md_file = request.files.get("md_file")
    if not md_file or not md_file.filename:
        return jsonify({"ok": False, "error": "请选择 Markdown 文件"}), 400
    orig_name = os.path.basename(md_file.filename)
    if not orig_name.lower().endswith(".md"):
        return jsonify({"ok": False, "error": "只接受 .md 文件"}), 400

    overwrite_id_raw = request.form.get("overwrite_id", "").strip()
    overwrite_id = overwrite_id_raw if valid_uuid(overwrite_id_raw) else None

    md_bytes = md_file.read()
    md_text  = md_bytes.decode("utf-8")
    md_size  = len(md_bytes)

    # Convert first (before touching DB/disk) so we can report errors early
    try:
        result    = convert(md_text, orig_name)
        status    = "ok"
        error_msg = ""
    except Exception as exc:
        result    = {"html": "", "title": os.path.splitext(orig_name)[0], "slide_count": 0}
        status    = "error"
        error_msg = str(exc)

    upload_time    = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    resource_files = request.files.getlist("resources")
    resource_names = [os.path.basename(f.filename) for f in resource_files if f.filename]

    db = get_db()

    if overwrite_id is not None:
        row = db.execute("SELECT id FROM presentations WHERE id=?", (overwrite_id,)).fetchone()
        if not row:
            overwrite_id = None  # fall back to insert

    if overwrite_id is not None:
        pres_id = overwrite_id
        old_dir = FILES_DIR / pres_id
        if old_dir.exists():
            shutil.rmtree(old_dir)
        db.execute(
            """UPDATE presentations
               SET title=?, filename=?, resources=?, upload_time=?,
                   md_size=?, slide_count=?, status=?, error_msg=?
             WHERE id=?""",
            (result["title"], orig_name, ",".join(resource_names), upload_time,
             md_size, result["slide_count"], status, error_msg, pres_id),
        )
    else:
        pres_id = str(uuid.uuid4())
        db.execute(
            """INSERT INTO presentations
               (id, title, filename, resources, upload_time, md_size, slide_count, status, error_msg)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (pres_id, result["title"], orig_name, ",".join(resource_names), upload_time,
             md_size, result["slide_count"], status, error_msg),
        )
    db.commit()

    # Save files to disk
    pres_dir = FILES_DIR / pres_id
    pres_dir.mkdir(exist_ok=True)

    (pres_dir / orig_name).write_bytes(md_bytes)

    for rf in resource_files:
        if rf.filename:
            rf.save(pres_dir / os.path.basename(rf.filename))

    if status == "ok":
        html = _rewrite_assets(result["html"], pres_id)
        (pres_dir / "presentation.html").write_text(html, encoding="utf-8")

    return jsonify({
        "ok":          status == "ok",
        "id":          pres_id,
        "title":       result["title"],
        "slide_count": result["slide_count"],
        "status":      status,
        "error":       error_msg,
    })


@app.route("/api/presentations/<string:pres_id>/regenerate", methods=["POST"])
def regenerate(pres_id):
    require_uuid(pres_id)
    db  = get_db()
    row = db.execute("SELECT * FROM presentations WHERE id=?", (pres_id,)).fetchone()
    if not row:
        return jsonify({"ok": False, "error": "Not found"}), 404

    pres_dir = FILES_DIR / pres_id
    md_path  = pres_dir / row["filename"]
    if not md_path.exists():
        return jsonify({"ok": False, "error": "原始 MD 文件不存在"}), 404

    md_text = md_path.read_text(encoding="utf-8")

    try:
        result    = convert(md_text, row["filename"])
        html      = _rewrite_assets(result["html"], pres_id)
        (pres_dir / "presentation.html").write_text(html, encoding="utf-8")
        status    = "ok"
        error_msg = ""
    except Exception as exc:
        result    = {"title": row["title"], "slide_count": 0}
        status    = "error"
        error_msg = str(exc)

    upload_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db.execute(
        "UPDATE presentations SET title=?, slide_count=?, status=?, error_msg=?, upload_time=? WHERE id=?",
        (result["title"], result["slide_count"], status, error_msg, upload_time, pres_id),
    )
    db.commit()

    return jsonify({"ok": status == "ok", "slide_count": result["slide_count"], "error": error_msg})


@app.route("/api/presentations/<string:pres_id>", methods=["DELETE"])
def delete_presentation(pres_id):
    require_uuid(pres_id)
    db  = get_db()
    row = db.execute("SELECT id FROM presentations WHERE id=?", (pres_id,)).fetchone()
    if not row:
        return jsonify({"ok": False, "error": "Not found"}), 404
    db.execute("DELETE FROM presentations WHERE id=?", (pres_id,))
    db.commit()
    pres_dir = FILES_DIR / pres_id
    if pres_dir.exists():
        shutil.rmtree(pres_dir)
    return jsonify({"ok": True})


@app.route("/play/<string:pres_id>")
def play(pres_id):
    require_uuid(pres_id)
    html_path = FILES_DIR / pres_id / "presentation.html"
    if not html_path.exists():
        abort(404)
    html = html_path.read_text(encoding="utf-8")
    # Inject <base> so bare asset filenames resolve to /files/{id}/ relative
    # to the current page URL, regardless of deployment subpath.
    base_tag = f'  <base href="../files/{pres_id}/">\n'
    html = html.replace("<head>\n", "<head>\n" + base_tag, 1)
    return Response(html, content_type="text/html; charset=utf-8")


@app.route("/files/<string:pres_id>/<path:filename>")
def serve_file(pres_id, filename):
    require_uuid(pres_id)
    if ".." in filename:
        abort(400)
    return send_from_directory(FILES_DIR / pres_id, filename)


# ── Entry point ───────────────────────────────────────────────────────────────
def main():
    init_db()
    app.run(host="0.0.0.0", port=5002, debug=True, use_reloader=True)


if __name__ == "__main__":
    main()
