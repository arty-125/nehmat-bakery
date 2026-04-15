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
    url_for, session, flash, jsonify,
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
SECRET_KEY_FILE      = BASE_DIR / ".secret_key"

ALLOWED_IMAGE_EXT = {"jpg", "jpeg", "png", "gif", "webp"}
ALLOWED_VIDEO_EXT = {"mp4", "webm", "ogg", "mov"}
ALLOWED_ALL_EXT   = ALLOWED_IMAGE_EXT | ALLOWED_VIDEO_EXT
MAX_UPLOAD_BYTES  = 50 * 1024 * 1024   # 50 MB

# ── App factory ──────────────────────────────────────────────────────────────
def _get_or_create_secret_key() -> str:
    if SECRET_KEY_FILE.exists():
        return SECRET_KEY_FILE.read_text().strip()
    key = secrets.token_hex(32)
    SECRET_KEY_FILE.write_text(key)
    return key


app = Flask(__name__)
app.config["SECRET_KEY"]          = _get_or_create_secret_key()
app.config["MAX_CONTENT_LENGTH"]  = MAX_UPLOAD_BYTES
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=8)

for _d in (DATA_DIR, PRODUCTS_UPLOAD_DIR, SLIDER_UPLOAD_DIR):
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
                    "description": (
                        "Baked fresh every morning — feather-light, "
                        "golden at the edges, and soft at the heart. "
                        "Made with pure flour and a touch of tradition."
                    ),
                    "image": None,
                },
                {
                    "id": 2, "order": 2,
                    "name": "Whole Wheat Taftoon Bread",
                    "name_fa": "نان تافتون سبوس‌دار",
                    "description": (
                        "Wholesome and nutty, baked from stone-ground "
                        "whole wheat. A heartier choice that honours "
                        "flavour and nutrition equally."
                    ),
                    "image": None,
                },
                {
                    "id": 3, "order": 3,
                    "name": "Sar Shir",
                    "name_fa": "سر شیر",
                    "description": (
                        "Velvety clotted cream, patiently skimmed from "
                        "fresh whole milk. Luxuriously rich — a perfect "
                        "companion for warm bread and honey."
                    ),
                    "image": None,
                },
                {
                    "id": 4, "order": 4,
                    "name": "Khame",
                    "name_fa": "خامه",
                    "description": (
                        "Silky fresh cream with a naturally gentle "
                        "sweetness. Made daily from the finest local "
                        "milk, beautiful in cooking or on its own."
                    ),
                    "image": None,
                },
                {
                    "id": 5, "order": 5,
                    "name": "Mast",
                    "name_fa": "ماست",
                    "description": (
                        "Thick, luscious homemade yogurt, naturally "
                        "fermented to a smooth and tangy perfection. "
                        "Rich in live cultures and pure flavour."
                    ),
                    "image": None,
                },
                {
                    "id": 6, "order": 6,
                    "name": "Doogh",
                    "name_fa": "دوغ",
                    "description": (
                        "A chilled, refreshing traditional yogurt drink "
                        "— lightly salted and naturally cooling. The "
                        "quintessential Persian table companion."
                    ),
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
                    "subcaption": "Fresh bread & dairy, made with love every morning.",
                },
                {
                    "id": "slide-2", "order": 2, "type": "image",
                    "file": None,
                    "caption": "Traditional Taftoon Bread",
                    "subcaption": "Honoring generations of Persian baking heritage.",
                },
                {
                    "id": "slide-3", "order": 3, "type": "image",
                    "file": None,
                    "caption": "Pure Homemade Dairy",
                    "subcaption": "Cream, yogurt, and doogh crafted fresh from local milk.",
                },
            ]
        })

    if not admin_file.exists():
        _write_json(admin_file, {
            "username": "admin",
            "password_hash": generate_password_hash("admin1234"),
        })


_seed_defaults()


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
    return render_template("index.html", products=products, slides=slides)


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

    caption    = request.form.get("caption", "").strip()[:200]
    subcaption = request.form.get("subcaption", "").strip()[:300]
    file       = request.files.get("file")

    data  = _read_json(DATA_DIR / "slider.json")
    items = data.get("items", [])

    saved_name = _save_upload(file, SLIDER_UPLOAD_DIR, ALLOWED_ALL_EXT)
    ftype = "image"
    if saved_name:
        ext   = saved_name.rsplit(".", 1)[-1].lower()
        ftype = "video" if ext in ALLOWED_VIDEO_EXT else "image"

    items.append({
        "id":         f"slide-{uuid.uuid4().hex[:8]}",
        "order":      len(items) + 1,
        "type":       ftype,
        "file":       saved_name,
        "caption":    caption,
        "subcaption": subcaption,
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

    caption    = request.form.get("caption", "").strip()[:200]
    subcaption = request.form.get("subcaption", "").strip()[:300]
    file       = request.files.get("file")

    for item in items:
        if item["id"] == slide_id:
            item["caption"]    = caption
            item["subcaption"] = subcaption
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

    name        = request.form.get("name", "").strip()[:100]
    name_fa     = request.form.get("name_fa", "").strip()[:100]
    description = request.form.get("description", "").strip()[:600]
    file        = request.files.get("image")

    data     = _read_json(DATA_DIR / "products.json")
    products = data.get("products", [])

    for p in products:
        if p["id"] == product_id:
            if name:        p["name"]        = name
            if name_fa:     p["name_fa"]     = name_fa
            if description: p["description"] = description
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
    app.run(debug=True, host="0.0.0.0", port=5000)
