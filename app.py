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
from datetime import date, datetime, timedelta
from functools import wraps

import bcrypt
try:
    import magic
    HAS_MAGIC = True
except ImportError:
    HAS_MAGIC = False
from dotenv import load_dotenv
from flask import Flask, request, jsonify, render_template, send_from_directory, session, redirect, url_for
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
    "Ruined linnen",
    "Scammer",
    "Animals",
    "Drug use",
    "Former employee on bad terms",
    "Stole property"
]


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
                    return creds
        except (json.JSONDecodeError, IOError):
            pass
    return None


def save_credentials(username: str, password_hash: str, manager_password_hash: str):
    """Save credentials to file securely."""
    creds = {
        'username': username,
        'password_hash': password_hash,
        'manager_password_hash': manager_password_hash,
        'created_at': datetime.now().isoformat()
    }
    with open(CREDENTIALS_FILE, 'w') as f:
        json.dump(creds, f, indent=2)
    # Attempt to set restrictive file permissions (Unix-like systems)
    try:
        os.chmod(CREDENTIALS_FILE, 0o600)
    except (OSError, AttributeError):
        pass  # Windows or permission issues


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
    Falls back to extension check if python-magic is not available.
    """
    if not HAS_MAGIC:
        # Fallback: just return a valid type (extension already checked)
        return 'image/jpeg'

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
            return redirect(url_for('setup'))
        if not session.get('logged_in'):
            return redirect(url_for('login'))
        # Refresh session on activity
        session.modified = True
        return f(*args, **kwargs)
    return decorated_function


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

        if errors:
            return render_template("setup.html", errors=errors)

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

        if username == LOGIN_USERNAME and verify_password(password, LOGIN_PASSWORD_HASH):
            session['logged_in'] = True
            session.permanent = True
            return redirect(url_for('home'))
        else:
            return render_template("login.html", error="Invalid username or password")

    return render_template("login.html")


@app.get("/logout")
def logout():
    session.clear()  # Clear entire session
    return redirect(url_for('login'))


@app.get("/")
@login_required
def home():
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


    # Sorting logic
    sort = request.args.get('sort', None)
    dir_ = request.args.get('dir', None)
    allowed_sorts = {
        'name': 'LOWER(guest_name)',
        'date': 'date_added',
        'status': 'status',
        'ban_type': 'ban_type'
    }
    allowed_dirs = {'asc', 'desc'}

    if sort in allowed_sorts and dir_ in allowed_dirs:
        order_by = f"{allowed_sorts[sort]} {dir_.upper()}"
    else:
        order_by = "date_added DESC"

    sql += f" ORDER BY {order_by}"

    conn = connect_db()
    records = conn.execute(sql, params).fetchall()

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
        "SELECT status, ban_type FROM records WHERE id = ?", (record_id,)
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
    """, (record_id, today, initials, f"Ban lifted. Type: {lift_type_display}. Reason: {lift_reason}"))

    conn.commit()
    conn.close()

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


@app.post("/api/settings/login")
@login_required
@limiter.limit("5 per minute")
def update_login_credentials():
    """Update login username and password."""
    global LOGIN_USERNAME, LOGIN_PASSWORD_HASH, CREDENTIALS

    data = request.json
    new_username = data.get('username', '').strip()[:50]
    new_password = data.get('password', '').strip()
    current_password = data.get('current_password', '').strip()

    # Validate current password using bcrypt
    if not verify_password(current_password, LOGIN_PASSWORD_HASH):
        return jsonify({"error": "Current password is incorrect"}), 401

    # Validation
    if not new_username or len(new_username) < 3:
        return jsonify({"error": "Username must be at least 3 characters"}), 400
    if not new_password or len(new_password) < 8:
        return jsonify({"error": "Password must be at least 8 characters"}), 400

    # Password strength check
    has_upper = any(c.isupper() for c in new_password)
    has_lower = any(c.islower() for c in new_password)
    has_digit = any(c.isdigit() for c in new_password)
    if not (has_upper and has_lower and has_digit):
        return jsonify({"error": "Password must contain uppercase, lowercase, and numbers"}), 400

    # Update credentials with bcrypt
    new_password_hash = hash_password(new_password)
    save_credentials(new_username, new_password_hash, MANAGER_PASSWORD_HASH)

    # Reload credentials
    CREDENTIALS = load_credentials()
    LOGIN_USERNAME = CREDENTIALS['username']
    LOGIN_PASSWORD_HASH = CREDENTIALS['password_hash']

    # Invalidate current session
    session.clear()

    return jsonify({"message": "Login credentials updated successfully"}), 200


@app.post("/api/settings/manager-password")
@login_required
@limiter.limit("5 per minute")
def update_manager_password():
    """Update manager password for lifting bans."""
    global MANAGER_PASSWORD_HASH, CREDENTIALS

    data = request.json
    new_manager_password = data.get('new_manager_password', '').strip()
    current_password = data.get('current_password', '').strip()

    # Validate current login password using bcrypt
    if not verify_password(current_password, LOGIN_PASSWORD_HASH):
        return jsonify({"error": "Current password is incorrect"}), 401

    # Validation
    if not new_manager_password or len(new_manager_password) < 8:
        return jsonify({"error": "Manager password must be at least 8 characters"}), 400

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

    # Only enable debug mode in development
    app.run(debug=not is_production, host='127.0.0.1')
