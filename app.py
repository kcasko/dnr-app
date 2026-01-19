"""
Restricted Guests Log (Do Not Rent System)
Internal staff reference system for hotel guest bans.

Security Features:
- bcrypt password hashing with salt
- CSRF protection via Flask-WTF
- Rate limiting on authentication endpoints
- Secure session configuration
- Security headers (CSP, X-Frame-Options, etc.)
- File upload validation with magic bytes
"""
import os
import sqlite3
import uuid
import json
import secrets
import re
from datetime import date, datetime, timedelta
from functools import wraps

import bcrypt
try:
    import magic
    HAS_MAGIC = True
except ImportError:
    HAS_MAGIC = False
try:
    import docx
    HAS_DOCX = True
except ImportError:
    HAS_DOCX = False
try:
    import pdfplumber
    HAS_PDF = True
    HAS_PDF_LAYOUT = True
except ImportError:
    HAS_PDF_LAYOUT = False
    try:
        from PyPDF2 import PdfReader
        HAS_PDF = True
    except ImportError:
        HAS_PDF = False
from dotenv import load_dotenv
from flask import Flask, request, jsonify, render_template, send_from_directory, session, redirect, url_for
from markupsafe import Markup, escape
from flask_wtf.csrf import CSRFProtect, generate_csrf
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Load environment variables from .env file
load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "dnr.db")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
CREDENTIALS_FILE = os.path.join(BASE_DIR, ".credentials")

# Ensure upload folder exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload

# Security: Require SECRET_KEY from environment, no fallback to insecure default
secret_key = os.environ.get('SECRET_KEY')
if not secret_key:
    # Generate a secure key and warn - in production this should be set in .env
    secret_key = secrets.token_hex(32)
    print("WARNING: SECRET_KEY not set in environment. Using generated key.")
    print("For production, set SECRET_KEY in .env file or environment variable.")
    print(f"Generated key (save this to .env): SECRET_KEY={secret_key}")
app.secret_key = secret_key

# Session security configuration
app.config['SESSION_COOKIE_SECURE'] = os.environ.get('FLASK_ENV') == 'production'  # HTTPS only in production
app.config['SESSION_COOKIE_HTTPONLY'] = True  # Prevent JavaScript access
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # CSRF protection
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=8)  # Session timeout

# CSRF Protection
app.config['WTF_CSRF_TIME_LIMIT'] = 3600  # CSRF token valid for 1 hour
app.config['WTF_CSRF_SSL_STRICT'] = os.environ.get('FLASK_ENV') == 'production'
csrf = CSRFProtect(app)

# Rate limiting
limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://",
)

# Allowed file extensions and MIME types for uploads
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
ALLOWED_MIME_TYPES = {
    'image/png': 'png',
    'image/jpeg': ['jpg', 'jpeg'],
    'image/gif': 'gif',
    'image/webp': 'webp'
}

# Predefined ban reasons
BAN_REASONS = [
    "Noise complaints multiple incidents",
    "Smoking in non smoking room",
    "Damage under review",
    "Housekeeping safety concern",
    "Aggressive or abusive behavior toward staff",
    "Policy violation warning issued",
    "Third party booking dispute",
    "Chargeback or payment dispute pending",
    "Local police involvement without arrest",
    "Welfare check initiated",
    "Ruined linen",
    "Scammer",
    "Animals",
    "Drug use",
    "Former employee on bad terms",
    "Stole property"
]

LOG_EDIT_WINDOW_MINUTES = 10
MAINTENANCE_EDIT_WINDOW_MINUTES = 10
IN_HOUSE_MESSAGE_EXPIRY_DAYS = 14

# Account lockout settings
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 15

# In-memory login attempt tracking (simple approach for single-instance use)
_login_attempts = {}  # {username: {'count': int, 'locked_until': datetime or None}}


def is_account_locked(username: str) -> bool:
    """Check if an account is currently locked due to failed login attempts."""
    if username not in _login_attempts:
        return False
    attempt_info = _login_attempts[username]
    if attempt_info.get('locked_until'):
        if datetime.now() < attempt_info['locked_until']:
            return True
        # Lockout expired, reset
        _login_attempts[username] = {'count': 0, 'locked_until': None}
    return False


def record_failed_login(username: str):
    """Record a failed login attempt and lock account if threshold reached."""
    if username not in _login_attempts:
        _login_attempts[username] = {'count': 0, 'locked_until': None}

    _login_attempts[username]['count'] += 1
    count = _login_attempts[username]['count']

    if count >= MAX_LOGIN_ATTEMPTS:
        _login_attempts[username]['locked_until'] = datetime.now() + timedelta(minutes=LOCKOUT_DURATION_MINUTES)
        print(f"Account locked: {username} (too many failed attempts)")


def reset_login_attempts(username: str):
    """Reset login attempts after successful login."""
    if username in _login_attempts:
        _login_attempts[username] = {'count': 0, 'locked_until': None}


def hash_password(password: str) -> str:
    """Hash a password using bcrypt with automatic salt generation."""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against a bcrypt hash."""
    try:
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
    except Exception:
        return False


def load_credentials():
    """Load credentials from file. Returns None if setup is required."""
    if os.path.exists(CREDENTIALS_FILE):
        try:
            with open(CREDENTIALS_FILE, 'r') as f:
                creds = json.load(f)
                # Validate required fields exist
                if all(k in creds for k in ['username', 'password_hash', 'manager_password_hash']):
                    # Ensure session_version exists (for backwards compatibility)
                    if 'session_version' not in creds:
                        creds['session_version'] = 1
                    return creds
        except (json.JSONDecodeError, IOError):
            pass
    return None


def save_credentials(username: str, password_hash: str, manager_password_hash: str, increment_session: bool = False):
    """Save credentials to file securely."""
    existing = load_credentials()
    session_version = 1
    if existing:
        session_version = existing.get('session_version', 1)
        if increment_session:
            session_version += 1

    creds = {
        'username': username,
        'password_hash': password_hash,
        'manager_password_hash': manager_password_hash,
        'session_version': session_version,
        'created_at': datetime.now().isoformat()
    }
    with open(CREDENTIALS_FILE, 'w') as f:
        json.dump(creds, f, indent=2)
    # Attempt to set restrictive file permissions (Unix-like systems)
    try:
        os.chmod(CREDENTIALS_FILE, 0o600)
    except (OSError, AttributeError):
        import platform
        if platform.system() == 'Windows':
            print("WARNING: File permissions cannot be enforced on Windows. Credentials file may be readable by other users.")
        else:
            print("WARNING: Could not set restrictive file permissions on credentials file.")


def is_setup_required() -> bool:
    """Check if initial setup is required (no credentials configured)."""
    return load_credentials() is None


# Load credentials
CREDENTIALS = load_credentials()
if CREDENTIALS:
    LOGIN_USERNAME = CREDENTIALS['username']
    LOGIN_PASSWORD_HASH = CREDENTIALS['password_hash']
    MANAGER_PASSWORD_HASH = CREDENTIALS['manager_password_hash']
else:
    LOGIN_USERNAME = None
    LOGIN_PASSWORD_HASH = None
    MANAGER_PASSWORD_HASH = None


def allowed_file(filename: str) -> bool:
    """Check if file extension is allowed."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def validate_file_type(file_stream) -> str | None:
    """
    Validate file type using magic bytes (file signature).
    Returns the detected MIME type if valid, None otherwise.
    Rejects uploads if python-magic is not available for security.
    """
    if not HAS_MAGIC:
        # Security: reject uploads if magic validation is unavailable
        return None

    try:
        # Read first 2048 bytes for magic detection
        header = file_stream.read(2048)
        file_stream.seek(0)  # Reset stream position

        mime = magic.Magic(mime=True)
        detected_mime = mime.from_buffer(header)

        if detected_mime in ALLOWED_MIME_TYPES:
            return detected_mime
        return None
    except Exception:
        return None


def parse_docx_paragraphs(file_stream) -> list[str]:
    if not HAS_DOCX:
        raise RuntimeError("python-docx is not installed")
    document = docx.Document(file_stream)
    paragraphs = []
    for paragraph in document.paragraphs:
        text = paragraph.text.strip()
        if text:
            paragraphs.append(text)
    return paragraphs


def parse_pdf_text(file_stream) -> str:
    if not HAS_PDF:
        raise RuntimeError("PDF support is not installed")
    if HAS_PDF_LAYOUT:
        with pdfplumber.open(file_stream) as pdf:
            pages = []
            for page in pdf.pages:
                try:
                    text = page.extract_text(x_tolerance=1, y_tolerance=1, layout=True) or ""
                except TypeError:
                    text = page.extract_text() or ""
                pages.append(text.rstrip())
        return "\n".join(pages).strip()
    reader = PdfReader(file_stream)
    pages = []
    for page in reader.pages:
        text = page.extract_text() or ""
        pages.append(text.rstrip())
    return "\n".join(pages).strip()


def parse_pdf_lines(file_stream) -> list[str]:
    text = parse_pdf_text(file_stream)
    lines = []
    for line in text.splitlines():
        cleaned = line.rstrip()
        if cleaned:
            lines.append(cleaned)
    return lines


def dict_factory(cursor, row):
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}


def connect_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = dict_factory
    return conn


def login_required(f):
    """Decorator to require login for routes."""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if is_setup_required():
            if request.path.startswith("/api/"):
                return jsonify({"error": "Setup required"}), 401
            return redirect(url_for('setup'))

        if not session.get('logged_in'):
            if request.path.startswith("/api/"):
                return jsonify({"error": "Unauthorized"}), 401
            return redirect(url_for('login'))

        # Check if session is still valid (password may have changed)
        creds = load_credentials()
        if creds:
            current_version = creds.get('session_version', 1)
            session_version = session.get('session_version', 0)
            if session_version < current_version:
                session.clear()
                if request.path.startswith("/api/"):
                    return jsonify({"error": "Session expired. Please log in again."}), 401
                return redirect(url_for('login'))

        # Refresh session on activity
        session.modified = True
        return f(*args, **kwargs)
    return decorated_function


def parse_db_timestamp(value: str) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        try:
            return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None


def is_editable_log_entry(entry: dict) -> bool:
    if entry.get("is_system_event"):
        return False
    created_at = parse_db_timestamp(entry.get("created_at"))
    if not created_at:
        return False
    # UX: Shift notes lock shortly after creation to protect handoff history.
    return datetime.now() - created_at <= timedelta(minutes=LOG_EDIT_WINDOW_MINUTES)


def is_editable_maintenance_item(item: dict) -> bool:
    created_at = parse_db_timestamp(item.get("created_at"))
    if not created_at:
        return False
    # UX: Maintenance details can only be adjusted shortly after logging.
    return datetime.now() - created_at <= timedelta(minutes=MAINTENANCE_EDIT_WINDOW_MINUTES)


def log_entry_summary(title: str, location: str | None) -> str:
    if location:
        return f"{location.strip()} {title.strip()}"
    return title.strip()


def local_timestamp() -> str:
    return datetime.now().isoformat(sep=" ", timespec="seconds")


def future_timestamp(days: int) -> str:
    return (datetime.now() + timedelta(days=days)).isoformat(sep=" ", timespec="seconds")


def normalize_datetime_input(value: str) -> str | None:
    if not value:
        return None
    if "T" in value and len(value) == 16:
        return value.replace("T", " ") + ":00"
    return value


def parse_date_input(value: str) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def housekeeping_due_today(start_date: date, end_date: date, today: date) -> bool:
    if not start_date or not end_date:
        return False
    if today < start_date or today > end_date:
        return False
    return (today - start_date).days % 2 == 0


def room_sort_key(room_number: str) -> tuple[int, str]:
    value = (room_number or "").strip()
    match = re.search(r"\d+", value)
    number = int(match.group(0)) if match else 999999
    return (number, value.lower())


def insert_log_entry(
    note: str,
    related_record_id=None,
    related_maintenance_id=None,
    is_system_event=False,
    author_name=None,
    created_at=None,
):
    if is_system_event:
        author_name = "System"
    if not author_name:
        raise ValueError("author_name is required for log entries")
    if not created_at:
        created_at = local_timestamp()
    conn = connect_db()
    conn.execute("""
        INSERT INTO log_entries (author_name, note, related_record_id, related_maintenance_id, is_system_event, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (author_name, note, related_record_id, related_maintenance_id, int(is_system_event), created_at))
    conn.commit()
    conn.close()


def insert_housekeeping_event(request_id: int, note: str):
    now = local_timestamp()
    conn = connect_db()
    conn.execute("""
        INSERT INTO housekeeping_request_events (housekeeping_request_id, note, is_system_event, created_at)
        VALUES (?, ?, 1, ?)
    """, (request_id, note, now))
    conn.commit()
    conn.close()


def warn_if_missing_tables():
    required_tables = {
        "log_entries",
        "maintenance_items",
        "room_issues",
        "staff_announcements",
        "important_numbers",
        "how_to_guides",
        "food_local_spots",
        "checklist_templates",
        "checklist_items",
        "in_house_messages",
        "housekeeping_requests",
        "housekeeping_request_events",
    }
    conn = connect_db()
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    conn.close()
    existing = {row["name"] for row in rows}
    missing = sorted(required_tables - existing)
    if missing:
        missing_list = ", ".join(missing)
        print("WARNING: Missing tables:", missing_list)
        print("Run: python migrate_add_log_maintenance.py")


def check_expired_bans():
    """Auto-expire temporary bans that have passed their expiration date."""
    today = str(date.today())
    conn = connect_db()

    # Find temporary bans with date-based expiration that have passed
    expired = conn.execute("""
        SELECT id FROM records
        WHERE status = 'active'
        AND ban_type = 'temporary'
        AND expiration_type = 'date'
        AND expiration_date <= ?
    """, (today,)).fetchall()

    for record in expired:
        conn.execute("""
            UPDATE records SET status = 'expired' WHERE id = ?
        """, (record['id'],))

        # Add system timeline entry
        conn.execute("""
            INSERT INTO timeline_entries (record_id, entry_date, note, is_system)
            VALUES (?, ?, 'Ban auto-expired based on expiration date', 1)
        """, (record['id'], today))

    conn.commit()
    conn.close()


# Security headers middleware
@app.after_request
def add_security_headers(response):
    """Add security headers to all responses."""
    # Prevent clickjacking
    response.headers['X-Frame-Options'] = 'DENY'
    # Prevent MIME type sniffing
    response.headers['X-Content-Type-Options'] = 'nosniff'
    # XSS protection (legacy browsers)
    response.headers['X-XSS-Protection'] = '1; mode=block'
    # Referrer policy
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    # Content Security Policy
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob:; "
        "font-src 'self'; "
        "frame-ancestors 'none'; "
        "form-action 'self';"
    )
    # Permissions Policy
    response.headers['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
    return response


# CSRF token endpoint for JavaScript requests
@app.route('/api/csrf-token', methods=['GET'])
def get_csrf_token():
    """Provide CSRF token for JavaScript API calls."""
    if is_setup_required():
        return jsonify({'csrf_token': generate_csrf()})
    if not session.get('logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    return jsonify({'csrf_token': generate_csrf()})


# Initial setup route
@app.route("/setup", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def setup():
    """Initial setup page - only accessible when no credentials exist."""
    global LOGIN_USERNAME, LOGIN_PASSWORD_HASH, MANAGER_PASSWORD_HASH, CREDENTIALS

    if not is_setup_required():
        return redirect(url_for('login'))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        manager_password = request.form.get("manager_password", "")
        confirm_manager = request.form.get("confirm_manager_password", "")
        errors = []

        # Validate username
        if not username or len(username) < 3:
            errors.append("Username must be at least 3 characters")

        # Validate login password
        if not password or len(password) < 8:
            errors.append("Password must be at least 8 characters")
        elif password != confirm_password:
            errors.append("Passwords do not match")

        # Validate manager password
        if not manager_password or len(manager_password) < 8:
            errors.append("Manager password must be at least 8 characters")
        elif manager_password != confirm_manager:
            errors.append("Manager passwords do not match")

        # Password strength check
        if password and len(password) >= 8:
            has_upper = any(c.isupper() for c in password)
            has_lower = any(c.islower() for c in password)
            has_digit = any(c.isdigit() for c in password)
            if not (has_upper and has_lower and has_digit):
                errors.append("Password must contain uppercase, lowercase, and numbers")

        if manager_password and len(manager_password) >= 8:
            has_upper = any(c.isupper() for c in manager_password)
            has_lower = any(c.islower() for c in manager_password)
            has_digit = any(c.isdigit() for c in manager_password)
            if not (has_upper and has_lower and has_digit):
                errors.append("Manager password must contain uppercase, lowercase, and numbers")

        if errors:
            errors_html = Markup("".join(f"<li>{escape(error)}</li>" for error in errors))
            return render_template("setup.html", errors=errors, errors_html=errors_html)

        # Create credentials
        password_hash = hash_password(password)
        manager_hash = hash_password(manager_password)
        save_credentials(username, password_hash, manager_hash)

        # Reload credentials
        CREDENTIALS = load_credentials()
        LOGIN_USERNAME = CREDENTIALS['username']
        LOGIN_PASSWORD_HASH = CREDENTIALS['password_hash']
        MANAGER_PASSWORD_HASH = CREDENTIALS['manager_password_hash']

        return redirect(url_for('login'))

    return render_template("setup.html")


# Routes
@app.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute")
def login():
    if is_setup_required():
        return redirect(url_for('setup'))

    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")

        # Check if account is locked (use a consistent key for lockout)
        lockout_key = username.lower() if username else "_anonymous_"
        if is_account_locked(lockout_key):
            # Return same error as invalid credentials to avoid revealing lockout status
            return render_template("login.html", error="Invalid username or password")

        if username == LOGIN_USERNAME and verify_password(password, LOGIN_PASSWORD_HASH):
            reset_login_attempts(lockout_key)
            session['logged_in'] = True
            session.permanent = True
            # Store session version to detect password changes
            creds = load_credentials()
            session['session_version'] = creds.get('session_version', 1) if creds else 1
            return redirect(url_for('overview'))
        else:
            record_failed_login(lockout_key)
            return render_template("login.html", error="Invalid username or password")

    return render_template("login.html")


@app.get("/logout")
def logout():
    session.clear()  # Clear session data
    return redirect(url_for('login'))


@app.get("/")
@app.get("/overview")
@login_required
def overview():
    conn = connect_db()
    active_dnr_count = conn.execute("""
        SELECT COUNT(*) AS count FROM records WHERE status = 'active'
    """).fetchone()["count"]
    room_out_of_order_count = conn.execute("""
        SELECT COUNT(*) AS count FROM room_issues
        WHERE state = 'active' AND status = 'out_of_order'
    """).fetchone()["count"]
    room_use_if_needed_count = conn.execute("""
        SELECT COUNT(*) AS count FROM room_issues
        WHERE state = 'active' AND status = 'use_if_needed'
    """).fetchone()["count"]
    open_maintenance_count = conn.execute("""
        SELECT COUNT(*) AS count FROM maintenance_items
        WHERE status IN ('open', 'in_progress', 'blocked')
    """).fetchone()["count"]
    recent_notes = conn.execute("""
        SELECT * FROM log_entries
        WHERE is_system_event = 0
        ORDER BY created_at DESC, id DESC
        LIMIT 5
    """).fetchall()
    now = local_timestamp()
    announcements = conn.execute("""
        SELECT * FROM staff_announcements
        WHERE is_active = 1
        AND (starts_at IS NULL OR starts_at <= ?)
        AND (ends_at IS NULL OR ends_at >= ?)
        ORDER BY created_at DESC, id DESC
    """, (now, now)).fetchall()
    conn.close()

    return render_template(
        "overview.html",
        active_dnr_count=active_dnr_count,
        room_out_of_order_count=room_out_of_order_count,
        room_use_if_needed_count=room_use_if_needed_count,
        open_maintenance_count=open_maintenance_count,
        recent_notes=recent_notes,
        announcements=announcements,
        last_updated=now,
    )


@app.get("/log-book")
@login_required
def log_book():
    conn = connect_db()
    entries = conn.execute("""
        SELECT * FROM log_entries
        ORDER BY created_at DESC, id DESC
    """).fetchall()
    conn.close()

    edit_id = request.args.get("edit", "").strip()
    editable_id = None
    if edit_id.isdigit():
        editable_id = int(edit_id)

    for entry in entries:
        entry["is_editable"] = is_editable_log_entry(entry)

    return render_template("log_book.html", entries=entries, editable_id=editable_id)


@app.get("/dnr")
@login_required
def dnr_list():
    check_expired_bans()
    return render_template("index.html", reasons=BAN_REASONS)


@app.get("/api/records")
@login_required
def get_records():
    """Get all records with optional filtering."""
    check_expired_bans()

    status_filter = request.args.get('status', '')
    ban_type_filter = request.args.get('ban_type', '')
    search = request.args.get('search', '').strip()

    sql = "SELECT * FROM records WHERE 1=1"
    params = []

    if status_filter:
        sql += " AND status = ?"
        params.append(status_filter)

    if ban_type_filter:
        sql += " AND ban_type = ?"
        params.append(ban_type_filter)

    if search:
        sql += " AND guest_name LIKE ?"
        params.append(f"%{search}%")


    sort = request.args.get("sort", "").strip()
    dir_ = request.args.get("dir", "").strip().lower()
    if dir_ not in {"asc", "desc"}:
        dir_ = "asc"
    if sort not in {"name", "last_name", "date", "status", "ban_type"}:
        sort = "name"
        dir_ = "asc"

    conn = connect_db()
    records = conn.execute(sql, params).fetchall()

    def date_key(value: str) -> str:
        return value or ""

    if sort == "name":
        records.sort(
            key=lambda r: (
                r.get("guest_name", "").lower(),
            )
        )
    elif sort == "last_name":
        def last_name_key(name: str) -> str:
            parts = name.strip().split()
            if not parts:
                return ""
            return parts[-1].lower()
        records.sort(
            key=lambda r: (
                last_name_key(r.get("guest_name", "")),
                r.get("guest_name", "").lower(),
            )
        )
    elif sort == "date":
        records.sort(key=lambda r: date_key(r.get("date_added", "")))
    elif sort == "status":
        records.sort(key=lambda r: (r.get("status", ""), r.get("guest_name", "").lower()))
    elif sort == "ban_type":
        records.sort(key=lambda r: (r.get("ban_type", ""), r.get("guest_name", "").lower()))

    if dir_ == "desc":
        records.reverse()

    # Parse reasons JSON for each record
    for record in records:
        if record.get('reasons'):
            try:
                record['reasons'] = json.loads(record['reasons'])
            except (json.JSONDecodeError, TypeError):
                record['reasons'] = [record['reasons']]
        # Keep first reason for backward compatibility in list view
        record['reason'] = record['reasons'][0] if record.get('reasons') else ''

    conn.close()

    return jsonify(records)


@app.post("/log-book/entries")
@login_required
@limiter.limit("10 per minute")
def add_log_entry():
    note = request.form.get("note", "").strip()[:2000]

    if not note:
        return redirect(url_for("log_book"))

    insert_log_entry(note, author_name="System", is_system_event=False)

    return redirect(url_for("log_book"))


@app.post("/log-book/entries/<int:entry_id>/edit")
@login_required
@limiter.limit("10 per minute")
def edit_log_entry(entry_id):
    conn = connect_db()
    entry = conn.execute("""
        SELECT * FROM log_entries WHERE id = ?
    """, (entry_id,)).fetchone()

    if not entry or entry.get("is_system_event"):
        conn.close()
        return redirect(url_for("log_book"))

    if not is_editable_log_entry(entry):
        conn.close()
        return redirect(url_for("log_book"))

    note = request.form.get("note", "").strip()[:2000]
    if not note:
        conn.close()
        return redirect(url_for("log_book", edit=entry_id))

    conn.execute("""
        UPDATE log_entries
        SET note = ?
        WHERE id = ?
    """, (note, entry_id))
    conn.commit()
    conn.close()


def archive_expired_housekeeping_requests(today: date):
    today_str = today.isoformat()
    now = local_timestamp()
    conn = connect_db()
    conn.execute("""
        UPDATE housekeeping_requests
        SET archived_at = ?, updated_at = ?
        WHERE archived_at IS NULL
        AND end_date < ?
    """, (now, now, today_str))
    conn.commit()
    conn.close()

    return redirect(url_for("log_book"))


@app.get("/maintenance")
@login_required
def maintenance_list():
    status_filter = request.args.get("status", "").strip()

    conn = connect_db()
    if status_filter in {"open", "in_progress", "blocked", "completed"}:
        items = conn.execute("""
            SELECT * FROM maintenance_items
            WHERE status = ?
            ORDER BY created_at DESC, id DESC
        """, (status_filter,)).fetchall()
    elif status_filter == "all":
        items = conn.execute("""
            SELECT * FROM maintenance_items
            ORDER BY created_at DESC, id DESC
        """).fetchall()
    else:
        items = conn.execute("""
            SELECT * FROM maintenance_items
            WHERE status IN ('open', 'in_progress')
            ORDER BY created_at DESC, id DESC
        """).fetchall()
        status_filter = "default"
    edit_id = request.args.get("edit", "").strip()
    editable_id = None
    if edit_id.isdigit():
        editable_id = int(edit_id)

    for item in items:
        item["is_editable"] = is_editable_maintenance_item(item)

    conn.close()

    return render_template("maintenance.html", items=items, status_filter=status_filter, editable_id=editable_id)


@app.post("/maintenance")
@login_required
@limiter.limit("10 per minute")
def add_maintenance_item():
    title = request.form.get("title", "").strip()[:200]
    description = request.form.get("description", "").strip()[:2000]
    location = request.form.get("location", "").strip()[:200]
    priority = request.form.get("priority", "medium").strip()

    if not title:
        return redirect(url_for("maintenance_list"))
    if priority not in {"low", "medium", "high", "urgent"}:
        priority = "medium"

    now = local_timestamp()
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO maintenance_items (title, description, location, priority, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (title, description or None, location or None, priority, now, now))
    maintenance_id = cursor.lastrowid
    conn.commit()
    conn.close()

    summary = log_entry_summary(title, location)
    insert_log_entry(f"Maintenance reported: {summary}", related_maintenance_id=maintenance_id, is_system_event=True)

    return redirect(url_for("maintenance_list"))


@app.post("/maintenance/<int:item_id>/edit")
@login_required
@limiter.limit("10 per minute")
def edit_maintenance_item(item_id):
    conn = connect_db()
    item = conn.execute("""
        SELECT * FROM maintenance_items WHERE id = ?
    """, (item_id,)).fetchone()

    if not item or not is_editable_maintenance_item(item):
        conn.close()
        return redirect(url_for("maintenance_list"))

    title = request.form.get("title", "").strip()[:200]
    description = request.form.get("description", "").strip()[:2000]
    location = request.form.get("location", "").strip()[:200]
    priority = request.form.get("priority", "medium").strip()

    if not title:
        conn.close()
        return redirect(url_for("maintenance_list", edit=item_id))
    if priority not in {"low", "medium", "high", "urgent"}:
        priority = "medium"

    now = local_timestamp()
    conn.execute("""
        UPDATE maintenance_items
        SET title = ?, description = ?, location = ?, priority = ?, updated_at = ?
        WHERE id = ?
    """, (title, description or None, location or None, priority, now, item_id))
    conn.commit()
    conn.close()

    return redirect(url_for("maintenance_list"))


@app.post("/maintenance/<int:item_id>/status")
@login_required
@limiter.limit("10 per minute")
def update_maintenance_status(item_id):
    new_status = request.form.get("status", "").strip()
    if new_status not in {"open", "in_progress", "blocked", "completed"}:
        return redirect(url_for("maintenance_list"))

    conn = connect_db()
    item = conn.execute("""
        SELECT * FROM maintenance_items WHERE id = ?
    """, (item_id,)).fetchone()

    if not item:
        conn.close()
        return redirect(url_for("maintenance_list"))

    if item.get("status") == new_status:
        conn.close()
        return redirect(url_for("maintenance_list"))

    now = datetime.now().isoformat(sep=" ", timespec="seconds")
    completed_at = now if new_status == "completed" else None
    conn.execute("""
        UPDATE maintenance_items
        SET status = ?, updated_at = ?, completed_at = ?
        WHERE id = ?
    """, (new_status, now, completed_at, item_id))
    conn.commit()
    conn.close()

    summary = log_entry_summary(item.get("title", ""), item.get("location"))
    if new_status == "in_progress":
        message = f"Maintenance started: {summary}"
    elif new_status == "completed":
        message = f"Maintenance completed: {summary}"
    elif new_status == "blocked":
        message = f"Maintenance blocked: {summary}"
    else:
        message = f"Maintenance updated ({new_status}): {summary}"

    insert_log_entry(message, related_maintenance_id=item_id, is_system_event=True)

    return redirect(url_for("maintenance_list"))


@app.get("/room-issues")
@login_required
def room_issues_list():
    conn = connect_db()
    issues = conn.execute("""
        SELECT * FROM room_issues
        ORDER BY state ASC, created_at DESC, id DESC
    """).fetchall()
    conn.close()

    return render_template("room_issues.html", issues=issues)


@app.post("/room-issues")
@login_required
@limiter.limit("10 per minute")
def add_room_issue():
    room_number = request.form.get("room_number", "").strip()[:20]
    status = request.form.get("status", "").strip()
    note = request.form.get("note", "").strip()[:1000]

    if not room_number:
        return redirect(url_for("room_issues_list"))
    if status not in {"out_of_order", "use_if_needed"}:
        return redirect(url_for("room_issues_list"))

    now = local_timestamp()
    conn = connect_db()
    conn.execute("""
        INSERT INTO room_issues (room_number, status, note, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?)
    """, (room_number, status, note or None, now, now))
    conn.commit()
    conn.close()

    return redirect(url_for("room_issues_list"))


@app.post("/room-issues/<int:issue_id>/status")
@login_required
@limiter.limit("10 per minute")
def update_room_issue_status(issue_id):
    status = request.form.get("status", "").strip()
    if status not in {"out_of_order", "use_if_needed"}:
        return redirect(url_for("room_issues_list"))

    now = local_timestamp()
    conn = connect_db()
    conn.execute("""
        UPDATE room_issues
        SET status = ?, updated_at = ?
        WHERE id = ?
    """, (status, now, issue_id))
    conn.commit()
    conn.close()

    return redirect(url_for("room_issues_list"))


@app.post("/room-issues/<int:issue_id>/state")
@login_required
@limiter.limit("10 per minute")
def update_room_issue_state(issue_id):
    state = request.form.get("state", "").strip()
    if state not in {"active", "resolved"}:
        return redirect(url_for("room_issues_list"))

    now = local_timestamp()
    resolved_at = now if state == "resolved" else None
    conn = connect_db()
    conn.execute("""
        UPDATE room_issues
        SET state = ?, resolved_at = ?, updated_at = ?
        WHERE id = ?
    """, (state, resolved_at, now, issue_id))
    conn.commit()
    conn.close()

    return redirect(url_for("room_issues_list"))


@app.get("/housekeeping-requests")
@login_required
def housekeeping_requests():
    today = date.today()
    archive_expired_housekeeping_requests(today)
    today_str = today.isoformat()

    conn = connect_db()
    candidates = conn.execute("""
        SELECT * FROM housekeeping_requests
        WHERE archived_at IS NULL
        AND start_date <= ?
        AND end_date >= ?
        ORDER BY start_date ASC, id DESC
    """, (today_str, today_str)).fetchall()
    conn.close()

    due_today = []
    for item in candidates:
        start_date = parse_date_input(item.get("start_date", ""))
        end_date = parse_date_input(item.get("end_date", ""))
        if housekeeping_due_today(start_date, end_date, today):
            due_today.append(item)

    due_today.sort(key=lambda item: room_sort_key(item.get("room_number", "")))

    edit_id = request.args.get("edit", "").strip()
    editable_id = int(edit_id) if edit_id.isdigit() else None

    return render_template(
        "housekeeping_requests.html",
        requests=due_today,
        print_rooms=[item.get("room_number", "") for item in due_today],
        editable_id=editable_id,
        today=today_str,
        error=request.args.get("error", "").strip(),
    )


@app.post("/housekeeping-requests")
@login_required
@limiter.limit("10 per minute")
def add_housekeeping_request():
    room_number = request.form.get("room_number", "").strip()[:20]
    start_raw = request.form.get("start_date", "").strip()
    end_raw = request.form.get("end_date", "").strip()
    notes = request.form.get("notes", "").strip()[:1000]

    start_date = parse_date_input(start_raw)
    end_date = parse_date_input(end_raw)

    if not room_number or not start_date or not end_date:
        return redirect(url_for("housekeeping_requests", error="missing"))
    if start_date > end_date:
        return redirect(url_for("housekeeping_requests", error="date_order"))

    now = local_timestamp()
    conn = connect_db()
    conn.execute("""
        INSERT INTO housekeeping_requests (room_number, start_date, end_date, frequency, notes, created_at, updated_at)
        VALUES (?, ?, ?, 'every_other_day', ?, ?, ?)
    """, (room_number, start_date.isoformat(), end_date.isoformat(), notes or None, now, now))
    conn.commit()
    conn.close()

    return redirect(url_for("housekeeping_requests"))


@app.post("/housekeeping-requests/<int:request_id>/edit")
@login_required
@limiter.limit("10 per minute")
def edit_housekeeping_request(request_id):
    start_raw = request.form.get("start_date", "").strip()
    end_raw = request.form.get("end_date", "").strip()
    notes = request.form.get("notes", "").strip()[:1000]

    start_date = parse_date_input(start_raw)
    end_date = parse_date_input(end_raw)

    if not start_date or not end_date:
        return redirect(url_for("housekeeping_requests", edit=request_id, error="missing"))
    if start_date > end_date:
        return redirect(url_for("housekeeping_requests", edit=request_id, error="date_order"))

    conn = connect_db()
    existing = conn.execute("""
        SELECT * FROM housekeeping_requests WHERE id = ?
    """, (request_id,)).fetchone()

    if not existing or existing.get("archived_at"):
        conn.close()
        return redirect(url_for("housekeeping_requests"))

    now = local_timestamp()
    archived_at = now if date.today() > end_date else None
    conn.execute("""
        UPDATE housekeeping_requests
        SET start_date = ?, end_date = ?, notes = ?, updated_at = ?, archived_at = ?
        WHERE id = ?
    """, (start_date.isoformat(), end_date.isoformat(), notes or None, now, archived_at, request_id))
    conn.commit()
    conn.close()

    change_bits = []
    if existing.get("start_date") != start_date.isoformat():
        change_bits.append(f"start {existing.get('start_date')} -> {start_date.isoformat()}")
    if existing.get("end_date") != end_date.isoformat():
        change_bits.append(f"end {existing.get('end_date')} -> {end_date.isoformat()}")
    if (existing.get("notes") or "") != (notes or ""):
        change_bits.append("notes updated")
    if change_bits:
        note = f"Housekeeping request updated for room {existing.get('room_number')}: {', '.join(change_bits)}"
        insert_housekeeping_event(request_id, note)

    return redirect(url_for("housekeeping_requests"))


@app.get("/staff-announcements")
@login_required
def staff_announcements_list():
    conn = connect_db()
    announcements = conn.execute("""
        SELECT * FROM staff_announcements
        ORDER BY created_at DESC, id DESC
    """).fetchall()
    conn.close()

    return render_template(
        "staff_announcements.html",
        announcements=announcements,
        error=request.args.get("error", "").strip(),
    )


@app.post("/staff-announcements")
@login_required
@limiter.limit("10 per minute")
def add_staff_announcement():
    message = request.form.get("message", "").strip()[:2000]
    starts_at = normalize_datetime_input(request.form.get("starts_at", "").strip())
    ends_at = normalize_datetime_input(request.form.get("ends_at", "").strip())

    if not message:
        return redirect(url_for("staff_announcements_list"))

    conn = connect_db()
    conn.execute("""
        INSERT INTO staff_announcements (message, starts_at, ends_at, is_active)
        VALUES (?, ?, ?, 1)
    """, (message, starts_at, ends_at))
    conn.commit()
    conn.close()

    return redirect(url_for("staff_announcements_list"))


@app.post("/staff-announcements/<int:announcement_id>/toggle")
@login_required
@limiter.limit("10 per minute")
def toggle_staff_announcement(announcement_id):
    is_active = request.form.get("is_active", "").strip()
    if is_active not in {"0", "1"}:
        return redirect(url_for("staff_announcements_list"))

    conn = connect_db()
    conn.execute("""
        UPDATE staff_announcements
        SET is_active = ?
        WHERE id = ?
    """, (int(is_active), announcement_id))
    conn.commit()
    conn.close()

    return redirect(url_for("staff_announcements_list"))


@app.post("/staff-announcements/<int:announcement_id>/delete")
@login_required
@limiter.limit("5 per minute")
def delete_staff_announcement(announcement_id):
    password = request.form.get("manager_password", "").strip()

    if not verify_password(password, MANAGER_PASSWORD_HASH):
        return redirect(url_for("staff_announcements_list", error="manager"))

    conn = connect_db()
    conn.execute("DELETE FROM staff_announcements WHERE id = ?", (announcement_id,))
    conn.commit()
    conn.close()

    return redirect(url_for("staff_announcements_list"))


@app.get("/food-local-spots")
@login_required
def food_local_spots_page():
    conn = connect_db()
    spots = conn.execute("""
        SELECT * FROM food_local_spots
        ORDER BY name ASC, id DESC
    """).fetchall()
    conn.close()

    return render_template(
        "food_local_spots.html",
        spots=spots,
        error=request.args.get("error", "").strip(),
    )


@app.get("/cleaning-checklists")
@login_required
def cleaning_checklists_page():
    conn = connect_db()
    templates = conn.execute("""
        SELECT * FROM checklist_templates
        WHERE is_active = 1
        ORDER BY id ASC
    """).fetchall()
    items = conn.execute("""
        SELECT * FROM checklist_items
        ORDER BY template_id ASC, position ASC, id ASC
    """).fetchall()
    conn.close()

    items_by_template = {}
    for item in items:
        items_by_template.setdefault(item["template_id"], []).append(item)

    items_html_by_template = {}
    for template_id, template_items in items_by_template.items():
        items_html = "".join(
            f"<li>{escape(entry.get('item_text', ''))}</li>"
            for entry in template_items
        )
        items_html_by_template[template_id] = Markup(items_html)

    return render_template(
        "cleaning_checklists.html",
        templates=templates,
        items_by_template=items_by_template,
        items_html_by_template=items_html_by_template,
        error=request.args.get("error", "").strip(),
    )


@app.get("/in-house-messages")
@login_required
def in_house_messages_page():
    recipient = request.args.get("recipient", "").strip()[:100]
    show_expired = request.args.get("show_expired", "").strip() == "1"
    error = request.args.get("error", "").strip()
    now = local_timestamp()

    conn = connect_db()
    if recipient:
        if show_expired:
            messages = conn.execute("""
                SELECT * FROM in_house_messages
                WHERE recipient_name = ?
                ORDER BY created_at DESC, id DESC
            """, (recipient,)).fetchall()
        else:
            messages = conn.execute("""
                SELECT * FROM in_house_messages
                WHERE recipient_name = ?
                AND (expires_at IS NULL OR expires_at > ?)
                ORDER BY created_at DESC, id DESC
            """, (recipient, now)).fetchall()
    else:
        messages = []
    conn.close()

    return render_template(
        "in_house_messages.html",
        recipient=recipient,
        messages=messages,
        show_expired=show_expired,
        error=error,
    )


@app.post("/in-house-messages")
@login_required
@limiter.limit("10 per minute")
def add_in_house_message():
    recipient = request.form.get("recipient_name", "").strip()[:100]
    body = request.form.get("message_body", "").strip()[:2000]

    if not recipient or not body:
        return redirect(url_for("in_house_messages_page", recipient=recipient))

    now = local_timestamp()
    expires_at = future_timestamp(IN_HOUSE_MESSAGE_EXPIRY_DAYS)
    conn = connect_db()
    conn.execute("""
        INSERT INTO in_house_messages
        (recipient_name, message_body, author_name, created_at, is_read, expires_at)
        VALUES (?, ?, 'System', ?, 0, ?)
    """, (recipient, body, now, expires_at))
    conn.commit()
    conn.close()

    return redirect(url_for("in_house_messages_page", recipient=recipient))


@app.post("/in-house-messages/<int:message_id>/read")
@login_required
@limiter.limit("10 per minute")
def mark_in_house_message_read(message_id):
    recipient = request.form.get("recipient", "").strip()[:100]
    conn = connect_db()
    conn.execute("""
        UPDATE in_house_messages
        SET is_read = 1, read_at = ?
        WHERE id = ?
    """, (local_timestamp(), message_id))
    conn.commit()
    conn.close()

    return redirect(url_for("in_house_messages_page", recipient=recipient))


@app.post("/in-house-messages/<int:message_id>/delete")
@login_required
@limiter.limit("5 per minute")
def delete_in_house_message(message_id):
    recipient = request.form.get("recipient", "").strip()[:100]
    password = request.form.get("manager_password", "").strip()

    if not verify_password(password, MANAGER_PASSWORD_HASH):
        return redirect(url_for("in_house_messages_page", recipient=recipient, error="manager"))

    conn = connect_db()
    conn.execute("DELETE FROM in_house_messages WHERE id = ?", (message_id,))
    conn.commit()
    conn.close()

    return redirect(url_for("in_house_messages_page", recipient=recipient))


@app.get("/api/records/<int:record_id>")
@login_required
def get_record(record_id):
    """Get a single record with timeline and photos."""
    conn = connect_db()

    record = conn.execute(
        "SELECT * FROM records WHERE id = ?", (record_id,)
    ).fetchone()

    if not record:
        conn.close()
        return jsonify({"error": "Record not found"}), 404

    # Parse reasons JSON
    if record.get('reasons'):
        try:
            record['reasons'] = json.loads(record['reasons'])
        except (json.JSONDecodeError, TypeError):
            record['reasons'] = [record['reasons']]

    timeline = conn.execute("""
        SELECT * FROM timeline_entries
        WHERE record_id = ?
        ORDER BY entry_date DESC, id DESC
    """, (record_id,)).fetchall()

    photos = conn.execute("""
        SELECT id, filename, original_name, upload_date FROM photos
        WHERE record_id = ?
        ORDER BY upload_date DESC
    """, (record_id,)).fetchall()

    conn.close()

    record['timeline'] = timeline
    record['photos'] = photos

    return jsonify(record)


@app.post("/api/records")
@login_required
def add_record():
    """Add a new ban record."""
    data = request.json

    guest_name = data.get('guest_name', '').strip()[:200]  # Max length
    ban_type = data.get('ban_type', '').strip()
    reasons = data.get('reasons', [])
    reason_detail = data.get('reason_detail', '').strip()[:1000]  # Max length
    staff_initials = data.get('staff_initials', '').strip()[:10]  # Max length
    incident_date = data.get('incident_date', '')
    expiration_type = data.get('expiration_type', '')
    expiration_date = data.get('expiration_date', '')

    # Validation
    if not guest_name:
        return jsonify({"error": "Guest name is required"}), 400
    if ban_type not in ('temporary', 'permanent'):
        return jsonify({"error": "Invalid ban type"}), 400
    if not reasons or len(reasons) == 0 or len(reasons) > 10:
        return jsonify({"error": "At least one reason is required (max 10)"}), 400
    if not staff_initials:
        return jsonify({"error": "Staff initials are required"}), 400

    # Sanitize reasons (only allow predefined reasons)
    valid_reasons = [r for r in reasons if r in BAN_REASONS]
    if not valid_reasons:
        return jsonify({"error": "At least one valid reason is required"}), 400

    # For temporary bans, require expiration type
    if ban_type == 'temporary' and not expiration_type:
        return jsonify({"error": "Expiration type required for temporary bans"}), 400

    # For date-based expiration, require date
    if expiration_type == 'date' and not expiration_date:
        return jsonify({"error": "Expiration date required"}), 400

    today = str(date.today())

    # Convert reasons array to JSON string
    reasons_json = json.dumps(valid_reasons)

    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO records
        (guest_name, status, ban_type, reasons, reason_detail, date_added, incident_date,
         expiration_type, expiration_date)
        VALUES (?, 'active', ?, ?, ?, ?, ?, ?, ?)
    """, (guest_name, ban_type, reasons_json, reason_detail or None, today, incident_date or None,
          expiration_type or None, expiration_date or None))

    record_id = cursor.lastrowid

    # Add initial timeline entry
    cursor.execute("""
        INSERT INTO timeline_entries (record_id, entry_date, staff_initials, note, is_system)
        VALUES (?, ?, ?, ?, 1)
    """, (record_id, today, staff_initials, f"Record created. {ban_type.capitalize()} ban added."))

    conn.commit()
    conn.close()

    return jsonify({"id": record_id, "message": "Record added successfully"}), 201


@app.post("/api/records/<int:record_id>/timeline")
@login_required
def add_timeline_entry(record_id):
    """Add a timeline entry to a record."""
    conn = connect_db()

    record = conn.execute(
        "SELECT status FROM records WHERE id = ?", (record_id,)
    ).fetchone()

    if not record:
        conn.close()
        return jsonify({"error": "Record not found"}), 404

    if record['status'] == 'lifted':
        conn.close()
        return jsonify({"error": "Cannot add notes to lifted records"}), 400

    data = request.json
    staff_initials = data.get('staff_initials', '').strip()[:10]
    note = data.get('note', '').strip()[:2000]  # Max length

    if not staff_initials:
        conn.close()
        return jsonify({"error": "Staff initials required"}), 400
    if not note:
        conn.close()
        return jsonify({"error": "Note is required"}), 400

    today = str(date.today())

    conn.execute("""
        INSERT INTO timeline_entries (record_id, entry_date, staff_initials, note, is_system)
        VALUES (?, ?, ?, ?, 0)
    """, (record_id, today, staff_initials, note))

    conn.commit()
    conn.close()

    return jsonify({"message": "Note added successfully"}), 201


@app.post("/api/records/<int:record_id>/photos")
@login_required
def upload_photo(record_id):
    """Upload a photo for a record (max 5 photos per record)."""
    conn = connect_db()

    record = conn.execute(
        "SELECT status FROM records WHERE id = ?", (record_id,)
    ).fetchone()

    if not record:
        conn.close()
        return jsonify({"error": "Record not found"}), 404

    if record['status'] == 'lifted':
        conn.close()
        return jsonify({"error": "Cannot add photos to lifted records"}), 400

    # Check photo count
    photo_count = conn.execute(
        "SELECT COUNT(*) as count FROM photos WHERE record_id = ?", (record_id,)
    ).fetchone()['count']

    if photo_count >= 5:
        conn.close()
        return jsonify({"error": "Maximum 5 photos allowed per record"}), 400

    if 'photo' not in request.files:
        conn.close()
        return jsonify({"error": "No photo provided"}), 400

    file = request.files['photo']

    if file.filename == '':
        conn.close()
        return jsonify({"error": "No file selected"}), 400

    if not allowed_file(file.filename):
        conn.close()
        return jsonify({"error": "Invalid file type. Allowed: PNG, JPG, JPEG, GIF, WEBP"}), 400

    # Validate file content using magic bytes
    detected_mime = validate_file_type(file.stream)
    if not detected_mime:
        conn.close()
        if not HAS_MAGIC:
            return jsonify({"error": "Photo uploads are temporarily unavailable. Please contact support."}), 503
        return jsonify({"error": "Invalid file content. File does not match declared type."}), 400

    # Generate unique filename with correct extension based on MIME type
    ext = file.filename.rsplit('.', 1)[1].lower()
    filename = f"{uuid.uuid4().hex}.{ext}"
    filepath = os.path.join(UPLOAD_FOLDER, filename)

    file.save(filepath)

    today = str(date.today())

    # Sanitize original filename for storage
    original_name = file.filename[:255] if file.filename else 'unknown'

    conn.execute("""
        INSERT INTO photos (record_id, filename, original_name, upload_date)
        VALUES (?, ?, ?, ?)
    """, (record_id, filename, original_name, today))

    conn.commit()
    conn.close()

    return jsonify({"message": "Photo uploaded successfully"}), 201


@app.get("/uploads/<filename>")
@login_required
def serve_upload(filename):
    """Serve uploaded photos."""
    # Sanitize filename to prevent path traversal
    if '..' in filename or '/' in filename or '\\' in filename:
        return jsonify({"error": "Invalid filename"}), 400
    return send_from_directory(UPLOAD_FOLDER, filename)


@app.post("/api/records/<int:record_id>/lift")
@login_required
@limiter.limit("5 per minute")
def lift_ban(record_id):
    """Lift a ban (requires manager password)."""
    data = request.json

    password = data.get('password', '')
    lift_type = data.get('lift_type', '').strip()
    lift_reason = data.get('lift_reason', '').strip()[:1000]
    initials = data.get('initials', '').strip()[:10]

    conn = connect_db()

    record = conn.execute(
        "SELECT status, ban_type, guest_name FROM records WHERE id = ?", (record_id,)
    ).fetchone()

    if not record:
        conn.close()
        return jsonify({"error": "Record not found"}), 404

    if record['status'] == 'lifted':
        conn.close()
        return jsonify({"error": "Record already lifted"}), 400

    # Verify password using bcrypt
    if not verify_password(password, MANAGER_PASSWORD_HASH):
        # Log failed attempt silently
        today = datetime.now().isoformat()
        ip = request.remote_addr or 'unknown'

        conn.execute("""
            INSERT INTO password_attempts (record_id, attempt_date, ip_address)
            VALUES (?, ?, ?)
        """, (record_id, today, ip))

        # Add hidden timeline entry for failed attempt
        conn.execute("""
            INSERT INTO timeline_entries (record_id, entry_date, note, is_system)
            VALUES (?, ?, 'Failed lift attempt logged', 1)
        """, (record_id, str(date.today())))

        conn.commit()
        conn.close()

        # Return generic error (don't reveal password was wrong)
        return jsonify({"error": "Unable to process request"}), 400

    # Validate required fields
    if lift_type not in ('manager_override', 'issue_resolved', 'error_entry'):
        conn.close()
        return jsonify({"error": "Invalid removal type"}), 400
    if not lift_reason:
        conn.close()
        return jsonify({"error": "Removal reason is required"}), 400
    if not initials:
        conn.close()
        return jsonify({"error": "Manager initials are required"}), 400

    today = str(date.today())

    # Update record
    conn.execute("""
        UPDATE records
        SET status = 'lifted',
            lifted_date = ?,
            lifted_type = ?,
            lifted_reason = ?,
            lifted_initials = ?
        WHERE id = ?
    """, (today, lift_type, lift_reason, initials, record_id))

    # Add timeline entry
    lift_type_display = {
        'manager_override': 'Manager Override',
        'issue_resolved': 'Issue Resolved',
        'error_entry': 'Error Entry'
    }.get(lift_type, lift_type)

    conn.execute("""
        INSERT INTO timeline_entries (record_id, entry_date, staff_initials, note, is_system)
        VALUES (?, ?, ?, ?, 1)
    """, (record_id, today, "System", f"Ban lifted. Type: {lift_type_display}. Reason: {lift_reason}"))

    conn.commit()
    conn.close()

    insert_log_entry(
        f"DNR removed for {record.get('guest_name', 'Unknown')}. Type: {lift_type_display}.",
        related_record_id=record_id,
        is_system_event=True,
    )

    return jsonify({"message": "Ban lifted successfully"}), 200


@app.delete("/api/photos/<int:photo_id>")
@login_required
def delete_photo(photo_id):
    """Delete a photo (only from non-lifted records)."""
    conn = connect_db()

    photo = conn.execute("""
        SELECT p.*, r.status
        FROM photos p
        JOIN records r ON p.record_id = r.id
        WHERE p.id = ?
    """, (photo_id,)).fetchone()

    if not photo:
        conn.close()
        return jsonify({"error": "Photo not found"}), 404

    if photo['status'] == 'lifted':
        conn.close()
        return jsonify({"error": "Cannot delete photos from lifted records"}), 400

    # Delete file
    filepath = os.path.join(UPLOAD_FOLDER, photo['filename'])
    if os.path.exists(filepath):
        os.remove(filepath)

    # Delete from database
    conn.execute("DELETE FROM photos WHERE id = ?", (photo_id,))
    conn.commit()
    conn.close()

    return jsonify({"message": "Photo deleted"}), 200


@app.get("/api/reasons")
@login_required
def get_reasons():
    """Get predefined ban reasons."""
    return jsonify(BAN_REASONS)


@app.get("/settings")
@login_required
def settings_page():
    """Settings page for managing credentials."""
    return render_template("settings.html")


@app.get("/important-numbers")
@login_required
def important_numbers_page():
    conn = connect_db()
    numbers = conn.execute("""
        SELECT * FROM important_numbers
        ORDER BY label ASC, id DESC
    """).fetchall()
    conn.close()

    return render_template(
        "important_numbers.html",
        numbers=numbers,
        error=request.args.get("error", "").strip(),
    )


@app.get("/how-to-guides")
@login_required
def how_to_guides_page():
    conn = connect_db()
    guides = conn.execute("""
        SELECT * FROM how_to_guides
        ORDER BY title ASC, id DESC
    """).fetchall()
    conn.close()

    return render_template(
        "how_to_guides.html",
        guides=guides,
        error=request.args.get("error", "").strip(),
    )


@app.post("/important-numbers")
@login_required
@limiter.limit("10 per minute")
def add_important_number():
    label = request.form.get("label", "").strip()[:200]
    phone = request.form.get("phone", "").strip()[:50]
    notes = request.form.get("notes", "").strip()[:1000]

    if not label or not phone:
        return redirect(url_for("important_numbers_page"))

    conn = connect_db()
    conn.execute("""
        INSERT INTO important_numbers (label, phone, notes, created_at)
        VALUES (?, ?, ?, ?)
    """, (label, phone, notes or None, local_timestamp()))
    conn.commit()
    conn.close()

    return redirect(url_for("important_numbers_page"))


@app.post("/important-numbers/<int:number_id>/delete")
@login_required
@limiter.limit("5 per minute")
def delete_important_number(number_id):
    password = request.form.get("manager_password", "").strip()
    if not verify_password(password, MANAGER_PASSWORD_HASH):
        return redirect(url_for("important_numbers_page", error="manager"))

    conn = connect_db()
    conn.execute("DELETE FROM important_numbers WHERE id = ?", (number_id,))
    conn.commit()
    conn.close()

    return redirect(url_for("important_numbers_page"))


@app.post("/how-to-guides")
@login_required
@limiter.limit("10 per minute")
def add_how_to_guide():
    title = request.form.get("title", "").strip()[:200]
    body = request.form.get("body", "").strip()[:4000]

    if not title or not body:
        return redirect(url_for("how_to_guides_page"))

    conn = connect_db()
    conn.execute("""
        INSERT INTO how_to_guides (title, body, created_at)
        VALUES (?, ?, ?)
    """, (title, body, local_timestamp()))
    conn.commit()
    conn.close()

    return redirect(url_for("how_to_guides_page"))


@app.post("/how-to-guides/import")
@login_required
@limiter.limit("5 per minute")
def import_how_to_guide():
    file = request.files.get("guide_file")
    if not file:
        return redirect(url_for("how_to_guides_page", error="file"))

    filename = file.filename.lower()
    if filename.endswith(".docx"):
        if not HAS_DOCX:
            return redirect(url_for("how_to_guides_page", error="docx"))
        try:
            paragraphs = parse_docx_paragraphs(file)
        except Exception:
            return redirect(url_for("how_to_guides_page", error="parse"))
    elif filename.endswith(".pdf"):
        if not HAS_PDF:
            return redirect(url_for("how_to_guides_page", error="pdf"))
        try:
            pdf_text = parse_pdf_text(file)
        except Exception:
            return redirect(url_for("how_to_guides_page", error="parse"))
    else:
        return redirect(url_for("how_to_guides_page", error="file"))

    title = os.path.splitext(file.filename)[0].strip()[:200]
    if filename.endswith(".pdf"):
        body = (pdf_text or "").strip()[:4000]
    else:
        if not paragraphs:
            return redirect(url_for("how_to_guides_page", error="empty"))
        body = "\n\n".join(paragraphs)[:4000]

    if not body:
        return redirect(url_for("how_to_guides_page", error="empty"))

    conn = connect_db()
    conn.execute("""
        INSERT INTO how_to_guides (title, body, created_at)
        VALUES (?, ?, ?)
    """, (title, body, local_timestamp()))
    conn.commit()
    conn.close()

    return redirect(url_for("how_to_guides_page"))


@app.post("/how-to-guides/<int:guide_id>/delete")
@login_required
@limiter.limit("5 per minute")
def delete_how_to_guide(guide_id):
    password = request.form.get("manager_password", "").strip()
    if not verify_password(password, MANAGER_PASSWORD_HASH):
        return redirect(url_for("how_to_guides_page", error="manager"))

    conn = connect_db()
    conn.execute("DELETE FROM how_to_guides WHERE id = ?", (guide_id,))
    conn.commit()
    conn.close()

    return redirect(url_for("how_to_guides_page"))


@app.post("/food-local-spots")
@login_required
@limiter.limit("10 per minute")
def add_food_local_spot():
    name = request.form.get("name", "").strip()[:200]
    address = request.form.get("address", "").strip()[:200]
    phone = request.form.get("phone", "").strip()[:50]
    notes = request.form.get("notes", "").strip()[:1000]

    if not name:
        return redirect(url_for("food_local_spots_page"))

    conn = connect_db()
    conn.execute("""
        INSERT INTO food_local_spots (name, address, phone, notes, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (name, address or None, phone or None, notes or None, local_timestamp()))
    conn.commit()
    conn.close()

    return redirect(url_for("food_local_spots_page"))


@app.post("/food-local-spots/<int:spot_id>/delete")
@login_required
@limiter.limit("5 per minute")
def delete_food_local_spot(spot_id):
    password = request.form.get("manager_password", "").strip()
    if not verify_password(password, MANAGER_PASSWORD_HASH):
        return redirect(url_for("food_local_spots_page", error="manager"))

    conn = connect_db()
    conn.execute("DELETE FROM food_local_spots WHERE id = ?", (spot_id,))
    conn.commit()
    conn.close()

    return redirect(url_for("food_local_spots_page"))


@app.post("/cleaning-checklists")
@login_required
@limiter.limit("5 per minute")
def add_cleaning_checklist():
    name = request.form.get("name", "").strip()[:200]
    description = request.form.get("description", "").strip()[:500]
    items_raw = request.form.get("items", "")
    items = [line.strip() for line in items_raw.splitlines() if line.strip()]

    if not name or not items:
        return redirect(url_for("cleaning_checklists_page"))

    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO checklist_templates (name, description, is_active)
        VALUES (?, ?, 1)
    """, (name, description or None))
    template_id = cursor.lastrowid

    rows = []
    for idx, item in enumerate(items, start=1):
        rows.append((template_id, idx, item[:500]))

    cursor.executemany("""
        INSERT INTO checklist_items (template_id, position, item_text)
        VALUES (?, ?, ?)
    """, rows)
    conn.commit()
    conn.close()

    return redirect(url_for("cleaning_checklists_page"))


@app.post("/cleaning-checklists/import")
@login_required
@limiter.limit("5 per minute")
def import_cleaning_checklist():
    file = request.files.get("checklist_file")
    if not file:
        return redirect(url_for("cleaning_checklists_page", error="file"))

    filename = file.filename.lower()
    if filename.endswith(".docx"):
        if not HAS_DOCX:
            return redirect(url_for("cleaning_checklists_page", error="docx"))
        try:
            paragraphs = parse_docx_paragraphs(file)
        except Exception:
            return redirect(url_for("cleaning_checklists_page", error="parse"))
    elif filename.endswith(".pdf"):
        if not HAS_PDF:
            return redirect(url_for("cleaning_checklists_page", error="pdf"))
        try:
            paragraphs = parse_pdf_lines(file)
        except Exception:
            return redirect(url_for("cleaning_checklists_page", error="parse"))
    else:
        return redirect(url_for("cleaning_checklists_page", error="file"))

    if not paragraphs:
        return redirect(url_for("cleaning_checklists_page", error="empty"))

    title = os.path.splitext(file.filename)[0].strip()[:200]
    items = [p[:500] for p in paragraphs]

    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO checklist_templates (name, description, is_active)
        VALUES (?, NULL, 1)
    """, (title,))
    template_id = cursor.lastrowid
    rows = []
    for idx, item in enumerate(items, start=1):
        rows.append((template_id, idx, item))
    cursor.executemany("""
        INSERT INTO checklist_items (template_id, position, item_text)
        VALUES (?, ?, ?)
    """, rows)
    conn.commit()
    conn.close()

    return redirect(url_for("cleaning_checklists_page"))


@app.post("/cleaning-checklists/<int:template_id>/delete")
@login_required
@limiter.limit("5 per minute")
def delete_cleaning_checklist(template_id):
    password = request.form.get("manager_password", "").strip()
    if not verify_password(password, MANAGER_PASSWORD_HASH):
        return redirect(url_for("cleaning_checklists_page", error="manager"))

    conn = connect_db()
    conn.execute("DELETE FROM checklist_items WHERE template_id = ?", (template_id,))
    conn.execute("DELETE FROM checklist_templates WHERE id = ?", (template_id,))
    conn.commit()
    conn.close()

    return redirect(url_for("cleaning_checklists_page"))


@app.post("/api/settings/manager-password")
@login_required
@limiter.limit("5 per minute")
def update_manager_password():
    """Update manager password for lifting bans."""
    global MANAGER_PASSWORD_HASH, CREDENTIALS

    data = request.json
    new_manager_password = data.get('new_manager_password', '').strip()
    confirm_manager_password = data.get('confirm_manager_password', '').strip()
    current_password = data.get('current_password', '').strip()

    # Validate current login password using bcrypt
    if not verify_password(current_password, LOGIN_PASSWORD_HASH):
        return jsonify({"error": "Current password is incorrect"}), 401

    # Validation
    if not new_manager_password or len(new_manager_password) < 8:
        return jsonify({"error": "Manager password must be at least 8 characters"}), 400

    # Server-side password confirmation check
    if new_manager_password != confirm_manager_password:
        return jsonify({"error": "Manager passwords do not match"}), 400

    # Password strength check
    has_upper = any(c.isupper() for c in new_manager_password)
    has_lower = any(c.islower() for c in new_manager_password)
    has_digit = any(c.isdigit() for c in new_manager_password)
    if not (has_upper and has_lower and has_digit):
        return jsonify({"error": "Manager password must contain uppercase, lowercase, and numbers"}), 400

    # Update manager password with bcrypt
    new_manager_password_hash = hash_password(new_manager_password)
    save_credentials(LOGIN_USERNAME, LOGIN_PASSWORD_HASH, new_manager_password_hash)

    # Reload credentials
    CREDENTIALS = load_credentials()
    MANAGER_PASSWORD_HASH = CREDENTIALS['manager_password_hash']

    return jsonify({"message": "Manager password updated successfully"}), 200


@app.post("/api/settings/login")
@login_required
@limiter.limit("5 per minute")
def update_login_credentials():
    """Update login username and password."""
    global LOGIN_USERNAME, LOGIN_PASSWORD_HASH, CREDENTIALS

    data = request.json
    new_username = data.get('username', '').strip()[:50]
    new_password = data.get('password', '').strip()
    confirm_password = data.get('confirm_password', '').strip()
    current_password = data.get('current_password', '').strip()

    # Validate current password using bcrypt
    if not verify_password(current_password, LOGIN_PASSWORD_HASH):
        return jsonify({"error": "Current password is incorrect"}), 401

    # Validation
    if not new_username or len(new_username) < 3:
        return jsonify({"error": "Username must be at least 3 characters"}), 400
    if not new_password or len(new_password) < 8:
        return jsonify({"error": "Password must be at least 8 characters"}), 400

    # Server-side password confirmation check
    if new_password != confirm_password:
        return jsonify({"error": "Passwords do not match"}), 400

    # Password strength check
    has_upper = any(c.isupper() for c in new_password)
    has_lower = any(c.islower() for c in new_password)
    has_digit = any(c.isdigit() for c in new_password)
    if not (has_upper and has_lower and has_digit):
        return jsonify({"error": "Password must contain uppercase, lowercase, and numbers"}), 400

    # Update credentials with bcrypt and increment session version to invalidate all sessions
    new_password_hash = hash_password(new_password)
    save_credentials(new_username, new_password_hash, MANAGER_PASSWORD_HASH, increment_session=True)

    # Reload credentials
    CREDENTIALS = load_credentials()
    LOGIN_USERNAME = CREDENTIALS['username']
    LOGIN_PASSWORD_HASH = CREDENTIALS['password_hash']

    # Clear current session (other sessions will be invalidated by version check)
    session.clear()

    return jsonify({"message": "Login credentials updated successfully"}), 200


# Error handlers
@app.errorhandler(429)
def ratelimit_handler(e):
    return jsonify({"error": "Too many requests. Please try again later."}), 429


@app.errorhandler(400)
def bad_request_handler(e):
    return jsonify({"error": "Bad request"}), 400


@app.errorhandler(500)
def internal_error_handler(e):
    return jsonify({"error": "Internal server error"}), 500


if __name__ == "__main__":
    is_production = os.environ.get('FLASK_ENV') == 'production'

    if not is_production:
        print(f"[DEV MODE] Database: {DB_PATH}")
        print(f"[DEV MODE] Upload folder: {UPLOAD_FOLDER}")
        print("[DEV MODE] Debug mode enabled - DO NOT USE IN PRODUCTION")
        warn_if_missing_tables()

    # Only enable debug mode in development
    app.run(debug=not is_production, host='127.0.0.1')
