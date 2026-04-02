import argparse
import json
import os
import re
import secrets
import urllib.parse
import urllib.request
import uuid
import shutil
import sqlite3
from datetime import datetime
from functools import wraps
from pathlib import Path
from flask import (
    Flask, request, jsonify, send_from_directory,
    render_template, Response, g, abort, session, redirect, url_for
)
from werkzeug.middleware.proxy_fix import ProxyFix

from dotenv import load_dotenv
load_dotenv()

from md2ppt.parser import parse_slides
from md2ppt.generator import generate_html
from md2ppt import __version__ as _APP_VERSION

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR  = Path(__file__).parent
DATA_DIR  = BASE_DIR / "data"
FILES_DIR = DATA_DIR / "files"
DB_PATH   = DATA_DIR / "md2ppt.db"
_SECRET_KEY_FILE = DATA_DIR / ".secret_key"

DATA_DIR.mkdir(exist_ok=True)
FILES_DIR.mkdir(exist_ok=True)

# ── Feishu OAuth ──────────────────────────────────────────────────────────────
FEISHU_APP_ID       = os.environ.get("FEISHU_APP_ID", "")
FEISHU_APP_SECRET   = os.environ.get("FEISHU_APP_SECRET", "")
FEISHU_REDIRECT_URI = os.environ.get("FEISHU_REDIRECT_URI", "")

# ── Username validation ────────────────────────────────────────────────────────
_USERNAME_RE = re.compile(r'^[a-zA-Z0-9\u4e00-\u9fa5]{1,20}$')

# ── Flask app ─────────────────────────────────────────────────────────────────
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 500 * 1024 * 1024   # 500 MB
# Support subpath deployment (e.g. /md2ppt/) via reverse proxy.
# Nginx must set: proxy_set_header X-Forwarded-Prefix /md2ppt;
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

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
            id           TEXT    PRIMARY KEY,
            title        TEXT    NOT NULL,
            filename     TEXT    NOT NULL,
            resources    TEXT    NOT NULL DEFAULT '',
            upload_time  TEXT    NOT NULL,
            md_size      INTEGER NOT NULL DEFAULT 0,
            slide_count  INTEGER NOT NULL DEFAULT 0,
            status       TEXT    NOT NULL DEFAULT 'ok',
            error_msg    TEXT    NOT NULL DEFAULT '',
            user_open_id TEXT    NOT NULL DEFAULT ''
        )
    """)
    # migrate existing databases that lack columns
    for col_sql in [
        "ALTER TABLE presentations ADD COLUMN user_open_id TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE presentations ADD COLUMN visibility   TEXT NOT NULL DEFAULT 'private'",
        "ALTER TABLE presentations ADD COLUMN user_name    TEXT NOT NULL DEFAULT ''",
    ]:
        try:
            conn.execute(col_sql)
        except sqlite3.OperationalError:
            pass  # column already exists
    conn.commit()
    conn.close()


def _feishu_enabled() -> bool:
    return bool(FEISHU_APP_ID and FEISHU_APP_SECRET)


def _feishu_post(url: str, data: dict, headers: dict | None = None) -> dict:
    import urllib.error
    body = json.dumps(data).encode()
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    if headers:
        for k, v in headers.items():
            req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except urllib.error.URLError as e:
        raise RuntimeError(f"飞书 API 请求失败：{e.reason}") from e
    except json.JSONDecodeError as e:
        raise RuntimeError("飞书 API 返回了无效的响应") from e


def _feishu_get(url: str, headers: dict | None = None) -> dict:
    import urllib.error
    req = urllib.request.Request(url, method="GET")
    if headers:
        for k, v in headers.items():
            req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except urllib.error.URLError as e:
        raise RuntimeError(f"飞书 API 请求失败：{e.reason}") from e
    except json.JSONDecodeError as e:
        raise RuntimeError("飞书 API 返回了无效的响应") from e


def _get_app_access_token() -> str:
    resp = _feishu_post(
        "https://open.feishu.cn/open-apis/auth/v3/app_access_token/internal",
        {"app_id": FEISHU_APP_ID, "app_secret": FEISHU_APP_SECRET},
    )
    if resp.get("code") != 0:
        raise RuntimeError(f"获取 app_access_token 失败: {resp.get('msg')}")
    return resp["app_access_token"]


def _exchange_code_for_user(code: str) -> dict:
    app_token = _get_app_access_token()
    token_resp = _feishu_post(
        "https://open.feishu.cn/open-apis/authen/v1/oidc/access_token",
        {"grant_type": "authorization_code", "code": code},
        {"Authorization": f"Bearer {app_token}"},
    )
    if token_resp.get("code") != 0:
        raise RuntimeError(f"获取用户 token 失败: {token_resp.get('msg')}")
    user_token = token_resp["data"]["access_token"]
    user_resp = _feishu_get(
        "https://open.feishu.cn/open-apis/authen/v1/user_info",
        {"Authorization": f"Bearer {user_token}"},
    )
    if user_resp.get("code") != 0:
        raise RuntimeError(f"获取用户信息失败: {user_resp.get('msg')}")
    return user_resp["data"]


def _current_uid() -> str:
    return session.get("user", {}).get("user_id", "")


def _current_uname() -> str:
    return session.get("user", {}).get("name", "")


def _get_or_create_secret_key() -> str:
    if _SECRET_KEY_FILE.exists():
        return _SECRET_KEY_FILE.read_text().strip()
    key = secrets.token_hex(32)
    _SECRET_KEY_FILE.write_text(key)
    return key


def create_app() -> Flask:
    app.secret_key = _get_or_create_secret_key()
    init_db()
    return app


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user" not in session:
            if request.path.startswith("/api/"):
                return jsonify({"ok": False, "error": "未登录"}), 401
            return redirect(url_for("login_page"))
        return f(*args, **kwargs)
    return decorated


# ── Auth routes ───────────────────────────────────────────────────────────────
@app.route("/login", methods=["GET", "POST"])
def login_page():
    if "user" in session:
        return redirect(url_for("index"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        if not _USERNAME_RE.match(username):
            return render_template("login.html",
                                   feishu_enabled=_feishu_enabled(),
                                   error="用户名只能包含字母、数字和中文，长度 1~20 个字符"), 400
        user_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, username))
        session["user"] = {"user_id": user_id, "name": username}
        return redirect(url_for("index"))
    return render_template("login.html", feishu_enabled=_feishu_enabled())


@app.route("/auth/feishu")
def auth_feishu():
    if not _feishu_enabled():
        return redirect(url_for("login_page"))
    state = secrets.token_urlsafe(16)
    session["oauth_state"] = state
    callback_uri = FEISHU_REDIRECT_URI or url_for("auth_callback", _external=True)
    params = urllib.parse.urlencode({
        "app_id":        FEISHU_APP_ID,
        "redirect_uri":  callback_uri,
        "response_type": "code",
        "scope":         "user:base,user:id",
        "state":         state,
    })
    return redirect(f"https://open.feishu.cn/open-apis/authen/v1/index?{params}")


@app.route("/auth/callback")
def auth_callback():
    code  = request.args.get("code", "")
    state = request.args.get("state", "")
    if not code or state != session.pop("oauth_state", None):
        return render_template("login.html", feishu_enabled=True,
                               error="登录失败：state 验证未通过"), 400
    try:
        user = _exchange_code_for_user(code)
        session["user"] = {
            "user_id":    user.get("open_id", ""),
            "name":       user.get("name", "") or user.get("en_name", ""),
            "avatar_url": user.get("avatar_url", ""),
        }
        return redirect(url_for("index"))
    except Exception as exc:
        return render_template("login.html", feishu_enabled=True,
                               error=f"登录失败：{exc}"), 500


@app.route("/auth/logout", methods=["POST"])
def auth_logout():
    session.clear()
    return redirect(url_for("login_page"))


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
        # Resources are stored in a flat per-presentation directory.
        # Reject duplicate basenames at upload time so basename rewrites stay unambiguous.
        basename = re.split(r'[/\\]', path)[-1]
        return f'{attr}={quote}{basename}{quote}'
    return _ASSET_RE.sub(replacer, html)


def _decode_markdown_bytes(md_bytes: bytes) -> str:
    return md_bytes.decode("utf-8-sig")


def _validate_resource_names(md_filename: str, resource_files) -> str | None:
    names = [os.path.basename(f.filename) for f in resource_files if f.filename]
    seen: set[str] = set()
    duplicates: set[str] = set()
    for name in names:
        if name in seen:
            duplicates.add(name)
        seen.add(name)

    collisions = duplicates.copy()
    if md_filename in seen:
        collisions.add(md_filename)

    if collisions:
        joined = "、".join(sorted(collisions))
        return (
            "资源文件名必须唯一，且不能与 Markdown 文件同名。"
            f"检测到冲突：{joined}"
        )
    return None


def convert(md_text: str, md_filename: str, author: str = "") -> dict:
    """Return dict with html, title, slide_count. Raises ValueError on failure."""
    slides = parse_slides(md_text)
    if not slides:
        raise ValueError("Markdown 中没有找到任何幻灯片（需要至少一个 # 一级标题）")
    fallback = os.path.splitext(md_filename)[0]
    title    = _extract_title(slides[0], fallback)
    html     = generate_html(slides, title=title, author=author)
    return {"html": html, "title": title, "slide_count": len(slides)}


# ── Routes ────────────────────────────────────────────────────────────────────
@app.route("/")
@login_required
def index():
    return render_template("index.html", version=_APP_VERSION, user=session.get("user"))


@app.route("/example.md")
@login_required
def download_example():
    return send_from_directory(BASE_DIR / "example", "example.md", as_attachment=True)


@app.route("/api/presentations")
@login_required
def list_presentations():
    uid = _current_uid()
    rows = get_db().execute(
        """SELECT * FROM presentations
           WHERE user_open_id = ?
              OR user_open_id = ''
              OR visibility   = 'public'
           ORDER BY upload_time DESC""",
        (uid,),
    ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["resources"] = [x for x in d["resources"].split(",") if x]
        d["is_owner"]  = (d["user_open_id"] == uid) or (d["user_open_id"] == "")
        result.append(d)
    return jsonify({"presentations": result})


@app.route("/api/check-filename")
@login_required
def check_filename():
    name = request.args.get("filename", "").strip() or request.args.get("name", "").strip()
    uid  = _current_uid()
    row = get_db().execute(
        "SELECT id, title, upload_time FROM presentations "
        "WHERE filename = ? AND user_open_id = ? ORDER BY upload_time DESC LIMIT 1",
        (name, uid),
    ).fetchone()
    if row:
        latest = dict(row)
        return jsonify({"exists": True, "latest": latest, **latest})
    return jsonify({"exists": False, "latest": None})


@app.route("/api/upload", methods=["POST"])
@login_required
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
    try:
        md_text = _decode_markdown_bytes(md_bytes)
    except UnicodeDecodeError:
        return jsonify({"ok": False, "error": "Markdown 文件必须是 UTF-8 编码（支持 BOM）"}), 400
    md_size  = len(md_bytes)

    # Convert first (before touching DB/disk) so we can report errors early
    try:
        result    = convert(md_text, orig_name, author=_current_uname())
        status    = "ok"
        error_msg = ""
    except Exception as exc:
        result    = {"html": "", "title": os.path.splitext(orig_name)[0], "slide_count": 0}
        status    = "error"
        error_msg = str(exc)

    upload_time    = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    resource_files = request.files.getlist("resources")
    resource_error = _validate_resource_names(orig_name, resource_files)
    if resource_error:
        return jsonify({"ok": False, "error": resource_error}), 400

    resource_names = [os.path.basename(rf.filename) for rf in resource_files if rf.filename]

    uid   = _current_uid()
    uname = _current_uname()
    db    = get_db()

    if overwrite_id is not None:
        row = db.execute(
            "SELECT id FROM presentations WHERE id=? AND user_open_id=?",
            (overwrite_id, uid),
        ).fetchone()
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
             WHERE id=? AND user_open_id=?""",
            (result["title"], orig_name, ",".join(resource_names), upload_time,
             0, result["slide_count"], status, error_msg, pres_id, uid),
        )
    else:
        pres_id = str(uuid.uuid4())
        db.execute(
            """INSERT INTO presentations
               (id, title, filename, resources, upload_time, md_size, slide_count,
                status, error_msg, user_open_id, user_name, visibility)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,'private')""",
            (pres_id, result["title"], orig_name, ",".join(resource_names), upload_time,
             0, result["slide_count"], status, error_msg, uid, uname),
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

    # Update output size: HTML + resource files
    output_size = sum(
        (pres_dir / f).stat().st_size
        for f in (["presentation.html"] if status == "ok" else []) + resource_names
        if (pres_dir / f).exists()
    )
    db.execute("UPDATE presentations SET md_size=? WHERE id=?", (output_size, pres_id))
    db.commit()

    return jsonify({
        "ok":          status == "ok",
        "id":          pres_id,
        "title":       result["title"],
        "slide_count": result["slide_count"],
        "status":      status,
        "error":       error_msg,
    })


@app.route("/api/presentations/<string:pres_id>/regenerate", methods=["POST"])
@login_required
def regenerate(pres_id):
    require_uuid(pres_id)
    uid = _current_uid()
    db  = get_db()
    row = db.execute(
        "SELECT * FROM presentations WHERE id=? AND user_open_id=?",
        (pres_id, uid),
    ).fetchone()
    if not row:
        return jsonify({"ok": False, "error": "Not found"}), 404

    pres_dir = FILES_DIR / pres_id
    md_path  = pres_dir / row["filename"]
    if not md_path.exists():
        return jsonify({"ok": False, "error": "原始 MD 文件不存在"}), 404

    try:
        md_text    = _decode_markdown_bytes(md_path.read_bytes())
        result    = convert(md_text, row["filename"], author=row["user_name"] or "")
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
@login_required
def delete_presentation(pres_id):
    require_uuid(pres_id)
    uid = _current_uid()
    db  = get_db()
    row = db.execute(
        "SELECT id FROM presentations WHERE id=? AND user_open_id=?",
        (pres_id, uid),
    ).fetchone()
    if not row:
        return jsonify({"ok": False, "error": "Not found"}), 404
    db.execute(
        "DELETE FROM presentations WHERE id=? AND user_open_id=?",
        (pres_id, uid),
    )
    db.commit()
    pres_dir = FILES_DIR / pres_id
    if pres_dir.exists():
        shutil.rmtree(pres_dir)
    return jsonify({"ok": True})


@app.route("/api/presentations/<string:pres_id>/share", methods=["POST"])
@login_required
def share_presentation(pres_id):
    require_uuid(pres_id)
    uid = _current_uid()
    db  = get_db()
    row = db.execute(
        "SELECT id FROM presentations WHERE id=? AND user_open_id=?", (pres_id, uid)
    ).fetchone()
    if not row:
        return jsonify({"ok": False, "error": "Not found"}), 404
    db.execute("UPDATE presentations SET visibility='public' WHERE id=?", (pres_id,))
    db.commit()
    return jsonify({"ok": True, "visibility": "public"})


@app.route("/api/presentations/<string:pres_id>/claim", methods=["POST"])
@login_required
def claim_presentation(pres_id):
    require_uuid(pres_id)
    uid   = _current_uid()
    uname = _current_uname()
    db    = get_db()
    row   = db.execute(
        "SELECT id FROM presentations WHERE id=? AND user_open_id=''", (pres_id,)
    ).fetchone()
    if not row:
        return jsonify({"ok": False, "error": "Not found or already owned"}), 404
    db.execute(
        "UPDATE presentations SET user_open_id=?, user_name=?, visibility='private' WHERE id=?",
        (uid, uname, pres_id),
    )
    db.commit()
    return jsonify({"ok": True})


@app.route("/api/presentations/<string:pres_id>/unshare", methods=["POST"])
@login_required
def unshare_presentation(pres_id):
    require_uuid(pres_id)
    uid = _current_uid()
    db  = get_db()
    row = db.execute(
        "SELECT id FROM presentations WHERE id=? AND user_open_id=?", (pres_id, uid)
    ).fetchone()
    if not row:
        return jsonify({"ok": False, "error": "Not found"}), 404
    db.execute("UPDATE presentations SET visibility='private' WHERE id=?", (pres_id,))
    db.commit()
    return jsonify({"ok": True, "visibility": "private"})


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
    parser = argparse.ArgumentParser(description="Run the md2ppt web UI")
    parser.add_argument("--host", default=os.environ.get("MD2PPT_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("MD2PPT_PORT", "5002")))
    parser.add_argument(
        "--debug",
        action="store_true",
        default=os.environ.get("MD2PPT_DEBUG", "").lower() in {"1", "true", "yes", "on"},
        help="Enable Flask debug mode for local development",
    )
    args = parser.parse_args()

    create_app().run(
        host=args.host,
        port=args.port,
        debug=args.debug,
        use_reloader=args.debug,
    )


if __name__ == "__main__":
    main()
