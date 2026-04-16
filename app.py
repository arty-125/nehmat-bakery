"""
Nehmat Bakery — Flask Web Application
======================================
Tech choices:
  • Flask  — lightweight, perfect for a content-managed brochure site; keeps
             full template control without Django's overhead.
  • JSON   — human-readable, zero-config, trivially back-up-able, and ideal
             for the ~20 records this site will ever hold. Writes are made
             atomic (write → rename) to prevent corruption.
  • filelock — portable advisory lock so concurrent admin tabs never
               interleave partial writes.

Default admin credentials (change in Admin → Settings):
  username: admin   password: admin1234
"""

import os
import json
import uuid
import secrets
from datetime import timedelta
from pathlib import Path
from functools import wraps

from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash, jsonify, make_response,
)
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
from filelock import FileLock

# ── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR             = Path(__file__).parent
DATA_DIR             = BASE_DIR / "data"
UPLOADS_DIR          = BASE_DIR / "static" / "uploads"
PRODUCTS_UPLOAD_DIR  = UPLOADS_DIR / "products"
SLIDER_UPLOAD_DIR    = UPLOADS_DIR / "slider"
CONTENT_UPLOAD_DIR   = UPLOADS_DIR / "content"
SECRET_KEY_FILE      = BASE_DIR / ".secret_key"
TRANSLATIONS_DIR     = BASE_DIR / "translations"

ALLOWED_IMAGE_EXT = {"jpg", "jpeg", "png", "gif", "webp"}
ALLOWED_VIDEO_EXT = {"mp4", "webm", "ogg", "mov"}
ALLOWED_ALL_EXT   = ALLOWED_IMAGE_EXT | ALLOWED_VIDEO_EXT
MAX_UPLOAD_BYTES  = 50 * 1024 * 1024   # 50 MB

# ── App factory ──────────────────────────────────────────────────────────────
def _get_or_create_secret_key() -> str:
    # Prefer environment variable (Railway / production)
    env_key = os.environ.get("SECRET_KEY")
    if env_key:
        return env_key
    if SECRET_KEY_FILE.exists():
        return SECRET_KEY_FILE.read_text().strip()
    key = secrets.token_hex(32)
    try:
        SECRET_KEY_FILE.write_text(key)
    except OSError:
        pass  # read-only fs — key is still returned for this process
    return key


app = Flask(__name__)
app.config["SECRET_KEY"]          = _get_or_create_secret_key()
app.config["MAX_CONTENT_LENGTH"]  = MAX_UPLOAD_BYTES
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=8)

for _d in (DATA_DIR, PRODUCTS_UPLOAD_DIR, SLIDER_UPLOAD_DIR, CONTENT_UPLOAD_DIR):
    _d.mkdir(parents=True, exist_ok=True)


# ── Atomic JSON helpers ──────────────────────────────────────────────────────
def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _write_json(path: Path, data: dict) -> None:
    """Write atomically: write to .tmp then rename, protected by a lock file."""
    lock_path = path.with_suffix(".lock")
    with FileLock(str(lock_path), timeout=5):
        tmp = path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        tmp.replace(path)


# ── i18n helpers ─────────────────────────────────────────────────────────────
def _load_translations() -> dict:
    result: dict = {}
    for lang in ("en", "fa"):
        path = TRANSLATIONS_DIR / f"{lang}.json"
        try:
            result[lang] = json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            result[lang] = {}
    return result


_translations: dict = _load_translations()


# ── Seed default data ────────────────────────────────────────────────────────
def _seed_defaults() -> None:
    products_file = DATA_DIR / "products.json"
    slider_file   = DATA_DIR / "slider.json"
    admin_file    = DATA_DIR / "admin.json"

    if not products_file.exists():
        _write_json(products_file, {
            "products": [
                {
                    "id": 1, "order": 1,
                    "name": "White Taftoon Bread",
                    "name_fa": "نان تافتون سفید",
                    "description": "Baked fresh every morning — feather-light, golden at the edges, and soft at the heart. Made with pure flour and a touch of tradition.",
                    "description_fa": "هر صبح تازه پخته می‌شود — سبک، طلایی از لبه‌ها و نرم در دل. با آرد خالص و لمسی از سنت.",
                    "image": None,
                },
                {
                    "id": 2, "order": 2,
                    "name": "Whole Wheat Taftoon Bread",
                    "name_fa": "نان تافتون سبوس‌دار",
                    "description": "Wholesome and nutty, baked from stone-ground whole wheat. A heartier choice that honours flavour and nutrition equally.",
                    "description_fa": "سالم و خوش‌طعم، با آرد گندم کامل آسیاب‌شده. انتخابی ماندگارتر که هم طعم دارد هم ارزش غذایی.",
                    "image": None,
                },
                {
                    "id": 3, "order": 3,
                    "name": "Sar Shir",
                    "name_fa": "سر شیر",
                    "description": "Velvety clotted cream, patiently skimmed from fresh whole milk. Luxuriously rich — a perfect companion for warm bread and honey.",
                    "description_fa": "سرشیر مخملی، با صبر از شیر کامل تازه گرفته شده. غنی و لوکس — همراه بی‌نظیر نان گرم و عسل.",
                    "image": None,
                },
                {
                    "id": 4, "order": 4,
                    "name": "Khame",
                    "name_fa": "خامه",
                    "description": "Silky fresh cream with a naturally gentle sweetness. Made daily from the finest local milk, beautiful in cooking or on its own.",
                    "description_fa": "خامه تازه با شیرینی ملایم طبیعی. هر روز از بهترین شیر محلی تهیه می‌شود، برای پخت یا به‌تنهایی.",
                    "image": None,
                },
                {
                    "id": 5, "order": 5,
                    "name": "Mast",
                    "name_fa": "ماست",
                    "description": "Thick, luscious homemade yogurt, naturally fermented to a smooth and tangy perfection. Rich in live cultures and pure flavour.",
                    "description_fa": "ماست خانگی غلیظ و مطبوع، با تخمیر طبیعی به کمال رسیده. سرشار از کشت‌های زنده و طعمی خالص.",
                    "image": None,
                },
                {
                    "id": 6, "order": 6,
                    "name": "Doogh",
                    "name_fa": "دوغ",
                    "description": "A chilled, refreshing traditional yogurt drink — lightly salted and naturally cooling. The quintessential Persian table companion.",
                    "description_fa": "نوشیدنی سنتی ماست — خنک، کمی شور و به‌طور طبیعی تازه‌کننده. همراه همیشگی سفره ایرانی.",
                    "image": None,
                },
            ]
        })

    if not slider_file.exists():
        _write_json(slider_file, {
            "items": [
                {
                    "id": "slide-1", "order": 1, "type": "image",
                    "file": None,
                    "caption": "Welcome to Nehmat Bakery",
                    "caption_fa": "به نانوایی نعمت خوش آمدید",
                    "subcaption": "Fresh bread & dairy, made with love every morning.",
                    "subcaption_fa": "نان تازه و لبنیات خانگی، هر صبح با عشق.",
                },
                {
                    "id": "slide-2", "order": 2, "type": "image",
                    "file": None,
                    "caption": "Traditional Taftoon Bread",
                    "caption_fa": "نان تافتون سنتی",
                    "subcaption": "Honoring generations of Persian baking heritage.",
                    "subcaption_fa": "پاسداشت نسل‌ها سنت نانوایی ایرانی.",
                },
                {
                    "id": "slide-3", "order": 3, "type": "image",
                    "file": None,
                    "caption": "Pure Homemade Dairy",
                    "caption_fa": "لبنیات خانگی خالص",
                    "subcaption": "Cream, yogurt, and doogh crafted fresh from local milk.",
                    "subcaption_fa": "خامه، ماست و دوغ، هر روز از شیر محلی تازه.",
                },
            ]
        })

    if not admin_file.exists():
        _write_json(admin_file, {
            "username": "admin",
            "password_hash": generate_password_hash("admin1234"),
        })

    content_file = DATA_DIR / "content.json"
    if not content_file.exists():
        _write_json(content_file, {
            "about": {
                "label":    "Our Story",
                "label_fa": "\u062f\u0627\u0633\u062a\u0627\u0646 \u0645\u0627",
                "heading":    "A Home Built on Bread & Love",
                "heading_fa": "\u062e\u0627\u0646\u0647\u200c\u0627\u06cc \u0628\u0631 \u067e\u0627\u06cc\u0647 \u0646\u0627\u0646 \u0648 \u0645\u062d\u0628\u062a",
                "body":    "Nehmat Bakery was born from a simple belief: that the best food comes from patient hands, honest ingredients, and a genuine love for the craft. Our traditional Taftoon breads are baked fresh each morning, and our dairy products are made from locally sourced milk \u2014 nothing added, nothing compromised.",
                "body_fa": "\u0646\u0627\u0646\u0648\u0627\u06cc\u06cc \u0646\u0639\u0645\u062a \u0627\u0632 \u06cc\u06a9 \u0628\u0627\u0648\u0631 \u0633\u0627\u062f\u0647 \u0645\u062a\u0648\u0644\u062f \u0634\u062f: \u0628\u0647\u062a\u0631\u06cc\u0646 \u063a\u0630\u0627 \u0627\u0632 \u062f\u0633\u062a\u0627\u0646 \u0635\u0628\u0648\u0631\u060c \u0645\u0648\u0627\u062f \u0627\u0648\u0644\u06cc\u0647 \u0633\u0627\u0644\u0645 \u0648 \u0639\u0634\u0642 \u0648\u0627\u0642\u0639\u06cc \u0628\u0647 \u06a9\u0627\u0631 \u0633\u0631\u0686\u0634\u0645\u0647 \u0645\u06cc\u200c\u06af\u06cc\u0631\u062f.",
                "image": None,
            },
            "why": {
                "label":    "Why Nehmat?",
                "label_fa": "\u0686\u0631\u0627 \u0646\u0639\u0645\u062a\u061f",
                "heading":    "Quality You Can Taste",
                "heading_fa": "\u06a9\u06cc\u0641\u06cc\u062a\u06cc \u06a9\u0647 \u0645\u06cc\u200c\u0686\u0634\u06cc\u062f",
                "subtext":    "Four reasons our neighbours keep coming back, morning after morning.",
                "subtext_fa": "\u0686\u0647\u0627\u0631 \u062f\u0644\u06cc\u0644 \u06a9\u0647 \u0647\u0645\u0633\u0627\u06cc\u06af\u0627\u0646 \u0645\u0627 \u0647\u0631 \u0635\u0628\u062d \u0628\u0627\u0632\u0645\u06cc\u200c\u06af\u0631\u062f\u0646\u062f.",
                "items": [
                    {"icon": "\U0001f33e", "title": "Pure Ingredients", "title_fa": "\u0645\u0648\u0627\u062f \u062e\u0627\u0644\u0635", "body": "No preservatives, no artificial additives. Just flour, water, and time.", "body_fa": "\u0628\u062f\u0648\u0646 \u0646\u06af\u0647\u062f\u0627\u0631\u0646\u062f\u0647\u060c \u0628\u062f\u0648\u0646 \u0627\u0641\u0632\u0648\u062f\u0646\u06cc \u0645\u0635\u0646\u0648\u0639\u06cc. \u0641\u0642\u0637 \u0622\u0631\u062f\u060c \u0622\u0628 \u0648 \u0635\u0628\u0631."},
                    {"icon": "\U0001f305", "title": "Baked Daily", "title_fa": "\u067e\u062e\u062a \u0631\u0648\u0632\u0627\u0646\u0647", "body": "Every loaf and batch of dairy is made fresh each morning \u2014 never yesterday's.", "body_fa": "\u0647\u0631 \u0642\u0631\u0635 \u0646\u0627\u0646 \u0648 \u0647\u0631 \u0628\u0633\u062a\u0647 \u0644\u0628\u0646\u06cc\u0627\u062a \u0647\u0631 \u0635\u0628\u062d \u062a\u0627\u0632\u0647 \u062a\u0647\u06cc\u0647 \u0645\u06cc\u200c\u0634\u0648\u062f."},
                    {"icon": "\U0001f3e1", "title": "Homemade Quality", "title_fa": "\u06a9\u06cc\u0641\u06cc\u062a \u062e\u0627\u0646\u06af\u06cc", "body": "A small home kitchen means personal attention in every single product.", "body_fa": "\u0622\u0634\u067e\u0632\u062e\u0627\u0646\u0647 \u06a9\u0648\u0686\u06a9 \u0628\u0647 \u0645\u0639\u0646\u0627\u06cc \u062a\u0648\u062c\u0647 \u0634\u062e\u0635\u06cc \u0628\u0647 \u0647\u0631 \u0645\u062d\u0635\u0648\u0644 \u0627\u0633\u062a."},
                    {"icon": "\u2764\ufe0f", "title": "Made with Care", "title_fa": "\u0628\u0627 \u0645\u062d\u0628\u062a", "body": "Traditional Persian recipes passed down through generations, lovingly preserved.", "body_fa": "\u062f\u0633\u062a\u0648\u0631\u0647\u0627\u06cc \u0633\u0646\u062a\u06cc \u0627\u06cc\u0631\u0627\u0646\u06cc \u06a9\u0647 \u0627\u0632 \u0646\u0633\u0644\u200c\u0647\u0627\u06cc \u0642\u062f\u06cc\u0645 \u0628\u0647 \u0627\u0631\u062b \u0631\u0633\u06cc\u062f\u0647\u200c\u0627\u0646\u062f \u0628\u0627 \u0639\u0634\u0642 \u062d\u0641\u0638 \u0634\u062f\u0647\u200c\u0627\u0646\u062f."},
                ],
            },
        })


_seed_defaults()


# ── Data migration (adds new fields to existing data safely) ─────────────────
def _migrate_data() -> None:
    products_file = DATA_DIR / "products.json"
    if products_file.exists():
        data    = _read_json(products_file)
        changed = False
        for p in data.get("products", []):
            if "description_fa" not in p:
                p["description_fa"] = ""
                changed = True
        if changed:
            _write_json(products_file, data)

    slider_file = DATA_DIR / "slider.json"
    if slider_file.exists():
        data    = _read_json(slider_file)
        changed = False
        for item in data.get("items", []):
            for field in ("caption_fa", "subcaption_fa"):
                if field not in item:
                    item[field] = ""
                    changed = True
        if changed:
            _write_json(slider_file, data)


_migrate_data()


# ── CSRF helpers ─────────────────────────────────────────────────────────────
def _get_csrf_token() -> str:
    if "_csrf" not in session:
        session["_csrf"] = secrets.token_hex(16)
    return session["_csrf"]


def _check_csrf() -> bool:
    """Accept CSRF token from a form field OR from a JSON body."""
    token = request.form.get("csrf_token")
    if token is None:
        payload = request.get_json(silent=True) or {}
        token = payload.get("csrf_token")
    return token == session.get("_csrf")


app.jinja_env.globals["csrf_token"] = _get_csrf_token


# ── i18n context processor ───────────────────────────────────────────────────
@app.context_processor
def inject_i18n() -> dict:
    lang = request.cookies.get("nb_lang", "fa")
    if "lang" in session:
        lang = session["lang"]
    if lang not in _translations:
        lang = "fa"
    trans    = _translations[lang]
    en_trans = _translations.get("en", {})

    def t(key: str) -> str:
        return trans.get(key) or en_trans.get(key) or key

    return dict(t=t, lang=lang, is_rtl=(lang == "fa"))


# ── Language switcher route ───────────────────────────────────────────────────
@app.route("/set-language/<lang>")
def set_language(lang: str):
    referrer = request.referrer or url_for("index")
    if lang not in ("en", "fa"):
        return redirect(referrer)
    session["lang"] = lang
    resp = make_response(redirect(referrer))
    resp.set_cookie("nb_lang", lang, max_age=30 * 24 * 3600, samesite="Lax")
    return resp


# ── Auth decorator ────────────────────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("admin_logged_in"):
            flash("Please log in to continue.", "warning")
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return wrapper


# ── Upload helper ─────────────────────────────────────────────────────────────
def _save_upload(file, dest_dir: Path, allowed: set) -> str | None:
    """Validate, rename to a UUID, save, return stored filename or None."""
    if not file or not file.filename:
        return None
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in allowed:
        return None
    stored_name = f"{uuid.uuid4().hex}.{ext}"
    file.save(str(dest_dir / stored_name))
    return stored_name


def _delete_upload(filename: str | None, directory: Path) -> None:
    if filename:
        p = directory / filename
        if p.exists():
            p.unlink()


# ═══════════════════════════════════════════════════════════════════════════════
# PUBLIC ROUTES
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/")
def index():
    products = sorted(
        _read_json(DATA_DIR / "products.json").get("products", []),
        key=lambda x: x.get("order", 99),
    )
    slides = sorted(
        _read_json(DATA_DIR / "slider.json").get("items", []),
        key=lambda x: x.get("order", 99),
    )
    content = _read_json(DATA_DIR / "content.json")
    return render_template("index.html", products=products, slides=slides, content=content)


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/contact")
def contact():
    return render_template("contact.html")


# ═══════════════════════════════════════════════════════════════════════════════
# ADMIN — AUTH
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if session.get("admin_logged_in"):
        return redirect(url_for("admin_dashboard"))

    if request.method == "POST":
        if not _check_csrf():
            flash("Invalid request. Please try again.", "danger")
            return redirect(url_for("admin_login"))

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        data     = _read_json(DATA_DIR / "admin.json")

        if username == data.get("username") and \
                check_password_hash(data.get("password_hash", ""), password):
            session["admin_logged_in"] = True
            session["admin_user"]      = username
            session.permanent          = True
            flash("Welcome back!", "success")
            return redirect(url_for("admin_dashboard"))

        flash("Invalid username or password.", "danger")

    return render_template("admin/login.html")


@app.route("/admin/logout")
def admin_logout():
    session.clear()
    flash("You have been signed out.", "info")
    return redirect(url_for("admin_login"))


# ═══════════════════════════════════════════════════════════════════════════════
# ADMIN — DASHBOARD
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/admin/")
@app.route("/admin/dashboard")
@login_required
def admin_dashboard():
    product_count = len(_read_json(DATA_DIR / "products.json").get("products", []))
    slide_count   = len(_read_json(DATA_DIR / "slider.json").get("items", []))
    return render_template(
        "admin/dashboard.html",
        product_count=product_count,
        slide_count=slide_count,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# ADMIN — SLIDER
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/admin/slider")
@login_required
def admin_slider():
    data   = _read_json(DATA_DIR / "slider.json")
    slides = sorted(data.get("items", []), key=lambda x: x.get("order", 99))
    return render_template("admin/slider.html", slides=slides)


@app.route("/admin/slider/upload", methods=["POST"])
@login_required
def admin_slider_upload():
    if not _check_csrf():
        flash("Invalid request.", "danger")
        return redirect(url_for("admin_slider"))

    caption       = request.form.get("caption",       "").strip()[:200]
    subcaption    = request.form.get("subcaption",    "").strip()[:300]
    caption_fa    = request.form.get("caption_fa",    "").strip()[:200]
    subcaption_fa = request.form.get("subcaption_fa", "").strip()[:300]
    file          = request.files.get("file")

    data  = _read_json(DATA_DIR / "slider.json")
    items = data.get("items", [])

    saved_name = _save_upload(file, SLIDER_UPLOAD_DIR, ALLOWED_ALL_EXT)
    ftype = "image"
    if saved_name:
        ext   = saved_name.rsplit(".", 1)[-1].lower()
        ftype = "video" if ext in ALLOWED_VIDEO_EXT else "image"

    items.append({
        "id":            f"slide-{uuid.uuid4().hex[:8]}",
        "order":         len(items) + 1,
        "type":          ftype,
        "file":          saved_name,
        "caption":       caption,
        "subcaption":    subcaption,
        "caption_fa":    caption_fa,
        "subcaption_fa": subcaption_fa,
    })
    data["items"] = items
    _write_json(DATA_DIR / "slider.json", data)
    flash("Slide added successfully.", "success")
    return redirect(url_for("admin_slider"))


@app.route("/admin/slider/update/<slide_id>", methods=["POST"])
@login_required
def admin_slider_update(slide_id):
    if not _check_csrf():
        flash("Invalid request.", "danger")
        return redirect(url_for("admin_slider"))

    data  = _read_json(DATA_DIR / "slider.json")
    items = data.get("items", [])

    caption       = request.form.get("caption",       "").strip()[:200]
    subcaption    = request.form.get("subcaption",    "").strip()[:300]
    caption_fa    = request.form.get("caption_fa",    "").strip()[:200]
    subcaption_fa = request.form.get("subcaption_fa", "").strip()[:300]
    file          = request.files.get("file")

    for item in items:
        if item["id"] == slide_id:
            item["caption"]       = caption
            item["subcaption"]    = subcaption
            item["caption_fa"]    = caption_fa
            item["subcaption_fa"] = subcaption_fa
            if file and file.filename:
                saved = _save_upload(file, SLIDER_UPLOAD_DIR, ALLOWED_ALL_EXT)
                if saved:
                    _delete_upload(item.get("file"), SLIDER_UPLOAD_DIR)
                    ext          = saved.rsplit(".", 1)[-1].lower()
                    item["type"] = "video" if ext in ALLOWED_VIDEO_EXT else "image"
                    item["file"] = saved
            break

    data["items"] = items
    _write_json(DATA_DIR / "slider.json", data)
    flash("Slide updated.", "success")
    return redirect(url_for("admin_slider"))


@app.route("/admin/slider/delete/<slide_id>", methods=["POST"])
@login_required
def admin_slider_delete(slide_id):
    if not _check_csrf():
        flash("Invalid request.", "danger")
        return redirect(url_for("admin_slider"))

    data  = _read_json(DATA_DIR / "slider.json")
    items = data.get("items", [])
    item  = next((i for i in items if i["id"] == slide_id), None)
    if item:
        _delete_upload(item.get("file"), SLIDER_UPLOAD_DIR)

    items = [i for i in items if i["id"] != slide_id]
    for idx, i in enumerate(items, 1):
        i["order"] = idx
    data["items"] = items
    _write_json(DATA_DIR / "slider.json", data)
    flash("Slide deleted.", "success")
    return redirect(url_for("admin_slider"))


@app.route("/admin/slider/reorder", methods=["POST"])
@login_required
def admin_slider_reorder():
    payload = request.get_json(silent=True) or {}
    if not _check_csrf():
        return jsonify({"error": "csrf"}), 403
    if not isinstance(payload.get("order"), list):
        return jsonify({"error": "invalid payload"}), 400

    data  = _read_json(DATA_DIR / "slider.json")
    index = {i["id"]: i for i in data.get("items", [])}
    new   = []
    for pos, sid in enumerate(payload["order"], 1):
        if sid in index:
            index[sid]["order"] = pos
            new.append(index[sid])
    data["items"] = new
    _write_json(DATA_DIR / "slider.json", data)
    return jsonify({"ok": True})


# ═══════════════════════════════════════════════════════════════════════════════
# ADMIN — PRODUCTS
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/admin/products")
@login_required
def admin_products():
    data     = _read_json(DATA_DIR / "products.json")
    products = sorted(data.get("products", []), key=lambda x: x.get("order", 99))
    return render_template("admin/products.html", products=products)


@app.route("/admin/products/update/<int:product_id>", methods=["POST"])
@login_required
def admin_product_update(product_id):
    if not _check_csrf():
        flash("Invalid request.", "danger")
        return redirect(url_for("admin_products"))

    name           = request.form.get("name",           "").strip()[:100]
    name_fa        = request.form.get("name_fa",        "").strip()[:100]
    description    = request.form.get("description",    "").strip()[:600]
    description_fa = request.form.get("description_fa", "").strip()[:600]
    file           = request.files.get("image")

    data     = _read_json(DATA_DIR / "products.json")
    products = data.get("products", [])

    for p in products:
        if p["id"] == product_id:
            if name:           p["name"]           = name
            if name_fa:        p["name_fa"]        = name_fa
            if description:    p["description"]    = description
            if description_fa: p["description_fa"] = description_fa
            if file and file.filename:
                saved = _save_upload(file, PRODUCTS_UPLOAD_DIR, ALLOWED_IMAGE_EXT)
                if saved:
                    _delete_upload(p.get("image"), PRODUCTS_UPLOAD_DIR)
                    p["image"] = saved
            break

    data["products"] = products
    _write_json(DATA_DIR / "products.json", data)
    flash("Product updated.", "success")
    return redirect(url_for("admin_products"))


# ═══════════════════════════════════════════════════════════════════════════════
# ADMIN — CONTENT (About Teaser & Why Section)
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/admin/content")
@login_required
def admin_content():
    content = _read_json(DATA_DIR / "content.json")
    return render_template("admin/content.html", content=content)


@app.route("/admin/content/update", methods=["POST"])
@login_required
def admin_content_update():
    if not _check_csrf():
        flash("Invalid request.", "danger")
        return redirect(url_for("admin_content"))

    content = _read_json(DATA_DIR / "content.json")

    # ── About section ─────────────────────────────────────────────────────────
    about = content.setdefault("about", {})
    for field in ("label", "label_fa", "heading", "heading_fa", "body", "body_fa"):
        val = request.form.get(f"about_{field}", "").strip()[:600]
        if val:
            about[field] = val

    image_file = request.files.get("about_image")
    if image_file and image_file.filename:
        saved = _save_upload(image_file, CONTENT_UPLOAD_DIR, ALLOWED_IMAGE_EXT)
        if saved:
            _delete_upload(about.get("image"), CONTENT_UPLOAD_DIR)
            about["image"] = saved

    # ── Why section ───────────────────────────────────────────────────────────
    why = content.setdefault("why", {})
    for field in ("label", "label_fa", "heading", "heading_fa", "subtext", "subtext_fa"):
        val = request.form.get(f"why_{field}", "").strip()[:600]
        if val:
            why[field] = val

    items = why.setdefault("items", [{}, {}, {}, {}])
    for i in range(4):
        item = items[i] if i < len(items) else {}
        for field in ("icon", "title", "title_fa", "body", "body_fa"):
            val = request.form.get(f"why_item_{i}_{field}", "").strip()[:300]
            if val:
                item[field] = val
        if i < len(items):
            items[i] = item
        else:
            items.append(item)
    why["items"] = items

    content["about"] = about
    content["why"]   = why
    _write_json(DATA_DIR / "content.json", content)
    flash("Content updated successfully.", "success")
    return redirect(url_for("admin_content"))


# ═══════════════════════════════════════════════════════════════════════════════
# ADMIN — SETTINGS
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/admin/settings", methods=["GET", "POST"])
@login_required
def admin_settings():
    if request.method == "POST":
        if not _check_csrf():
            flash("Invalid request.", "danger")
            return redirect(url_for("admin_settings"))

        data       = _read_json(DATA_DIR / "admin.json")
        current_pw = request.form.get("current_password", "")
        new_pw     = request.form.get("new_password", "")
        confirm_pw = request.form.get("confirm_password", "")

        if not check_password_hash(data.get("password_hash", ""), current_pw):
            flash("Current password is incorrect.", "danger")
        elif len(new_pw) < 8:
            flash("New password must be at least 8 characters.", "danger")
        elif new_pw != confirm_pw:
            flash("Passwords do not match.", "danger")
        else:
            data["password_hash"] = generate_password_hash(new_pw)
            _write_json(DATA_DIR / "admin.json", data)
            flash("Password updated successfully.", "success")

    return render_template("admin/settings.html")


# ═══════════════════════════════════════════════════════════════════════════════
# ERROR HANDLERS
# ═══════════════════════════════════════════════════════════════════════════════
@app.errorhandler(404)
def not_found(_):
    return render_template("404.html"), 404


@app.errorhandler(413)
def file_too_large(_):
    flash("File is too large. Maximum size is 50 MB.", "danger")
    return redirect(request.referrer or url_for("admin_dashboard"))


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host="0.0.0.0", port=port)
