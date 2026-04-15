# Nehmat Bakery Website

A complete, production-ready website for a home bakery business — built with Flask, vanilla HTML/CSS/JS, and JSON file storage.

---

## Tech Stack & Rationale

| Layer | Choice | Why |
|---|---|---|
| **Backend** | Flask 3 | Lightweight, full template support, perfect for brochure + admin at this scale |
| **Storage** | JSON files | Zero config, human-readable, trivially back-up-able, right-sized for ~20 records |
| **Auth** | Werkzeug `generate_password_hash` | Bcrypt-powered, ships with Flask, no extra deps |
| **Concurrency** | `filelock` + atomic rename | Prevents JSON corruption without a database |
| **Frontend** | Vanilla HTML5/CSS3/JS | No build toolchain, fast load, easy to maintain |

---

## Project Structure

```
Nehmat-Bakery/
├── app.py                      # Flask application (all routes)
├── requirements.txt
├── .secret_key                 # Auto-generated on first run (do not commit)
│
├── data/                       # JSON data (auto-seeded on first run)
│   ├── products.json
│   ├── slider.json
│   └── admin.json              # Hashed credentials
│
├── static/
│   ├── css/
│   │   ├── style.css           # Public site styles
│   │   └── admin.css           # Admin panel styles
│   ├── js/
│   │   ├── main.js             # Slider, mobile nav, scroll-reveal
│   │   └── admin.js            # Drag-reorder, expand forms, toasts
│   └── uploads/
│       ├── products/           # Product images (gitignored)
│       └── slider/             # Slider images & videos (gitignored)
│
└── templates/
    ├── base.html               # Public base (header + footer)
    ├── index.html              # Home (hero slider + products + teasers)
    ├── about.html
    ├── contact.html
    ├── 404.html
    └── admin/
        ├── base.html           # Admin layout (sidebar)
        ├── login.html
        ├── dashboard.html
        ├── slider.html
        ├── products.html
        └── settings.html
```

---

## Quick Start

### 1. Create a virtual environment

```bash
# Windows (PowerShell)
python -m venv venv
.\venv\Scripts\Activate.ps1

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Run the development server

```bash
python app.py
```

Open **http://localhost:5000** in your browser.

### 4. Access the admin panel

Navigate to **http://localhost:5000/admin/login**

| Field | Default value |
|---|---|
| Username | `admin` |
| Password | `admin1234` |

> **Important:** Change the password immediately after first login via Admin → Settings.

---

## Admin Features

### Slider
- Upload images (JPG, PNG, GIF, WebP) or videos (MP4, WebM)
- Edit caption and sub-caption for each slide
- Delete slides (also removes the uploaded file)
- Drag rows to reorder; order is saved via AJAX

### Products
- Edit all 6 product cards: English name, Persian name, description, image
- Upload a product photo (replaces the gradient placeholder)

### Settings
- Change admin password (minimum 8 characters, bcrypt-hashed)

---

## Security Notes

- Passwords are hashed with Werkzeug's `pbkdf2:sha256` (bcrypt-compatible).
- A persistent, randomly generated `SECRET_KEY` is stored in `.secret_key` — never commit this file.
- CSRF tokens are validated on every admin POST request.
- Uploaded files are renamed to UUID-based names; original filenames are discarded.
- Only whitelisted extensions are accepted (image: jpg/jpeg/png/gif/webp; video: mp4/webm/ogg).
- Admin routes are protected by a `@login_required` decorator.

---

## Backup

All data lives in two folders:

```
data/           ← JSON content
static/uploads/ ← Images and videos
```

Copy these two folders to back up everything. To restore, paste them back and restart.

---

## Deploying to a VPS / Hosting

1. Install Python 3.11+ and `pip`.
2. Clone or copy the project.
3. `pip install -r requirements.txt`
4. Run behind a production WSGI server (recommended: **Gunicorn**):

```bash
pip install gunicorn
gunicorn -w 2 -b 0.0.0.0:8000 app:app
```

5. Put **Nginx** in front as a reverse proxy and serve `static/` directly.
6. Set the `SECRET_KEY` environment variable instead of relying on the file for production:

```bash
export SECRET_KEY="your-very-long-random-string"
```

---

## Future Improvements

| Feature | Effort |
|---|---|
| Online ordering form with Telegram bot notification | Medium |
| Multi-language support (Persian / English toggle) | Medium |
| Product categories & filtering | Low |
| SEO sitemap + meta tags per page | Low |
| Image compression/resizing on upload (Pillow) | Low |
| Migrate data to SQLite if product count grows > 50 | Low |
| WhatsApp / phone order button | Low |
