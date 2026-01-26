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
import logging
from datetime import date, datetime, timedelta
from functools import wraps
from zoneinfo import ZoneInfo
import shift_utils

TIMEZONE = ZoneInfo("America/New_York")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

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
DB_PATH = os.environ.get("DB_PATH") or os.path.join(BASE_DIR, "dnr.db")
UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER") or os.path.join(BASE_DIR, "uploads")
CREDENTIALS_FILE = os.environ.get("CREDENTIALS_FILE") or os.path.join(BASE_DIR, ".credentials")

# Ensure upload folder exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload

# Security: Require SECRET_KEY from environment, no fallback to insecure default
secret_key = os.environ.get('SECRET_KEY')
if not secret_key:
    # Generate a secure key and warn - in production this should be set in .env
    secret_key = secrets.token_hex(32)
    logger.warning("SECRET_KEY not set in environment. Using generated key.")
    logger.warning("For production, set SECRET_KEY in .env file or environment variable.")
    logger.info(f"Generated key (save this to .env): SECRET_KEY={secret_key}")
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
if os.environ.get('FLASK_ENV') == 'testing':
    app.config['RATELIMIT_ENABLED'] = False

limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://",
)

# Allowed file extensions and MIME types for uploads
# Allowed file extensions and MIME types for uploads
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'pdf', 'docx'}
ALLOWED_MIME_TYPES = {
    'image/png': 'png',
    'image/jpeg': ['jpg', 'jpeg'],
    'image/gif': 'gif',
    'image/webp': 'webp',
    'application/pdf': 'pdf',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'docx'
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
IN_HOUSE_MESSAGE_EXPIRY_DAYS = 7

# Account lockout settings
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 15


def is_account_locked(username: str) -> bool:
    """Check if an account is currently locked due to failed login attempts."""
    conn = get_db_connection()
    attempt = conn.execute("SELECT locked_until FROM login_attempts WHERE username = ?", (username,)).fetchone()
    conn.close()

    if not attempt or not attempt['locked_until']:
        return False

    try:
        locked_until = datetime.fromisoformat(attempt['locked_until'])
        if datetime.now() < locked_until:
            return True
        else:
            # Lockout expired, reset
            conn = get_db_connection()
            conn.execute("UPDATE login_attempts SET attempt_count = 0, locked_until = NULL WHERE username = ?", (username,))
            conn.commit()
            conn.close()
            return False
    except (ValueError, TypeError):
        return False


def record_failed_login(username: str):
    """Record a failed login attempt and lock account if threshold reached."""
    conn = get_db_connection()

    # Get or create login attempt record
    attempt = conn.execute("SELECT attempt_count FROM login_attempts WHERE username = ?", (username,)).fetchone()

    if attempt:
        new_count = attempt['attempt_count'] + 1
    else:
        new_count = 1

    locked_until = None
    if new_count >= MAX_LOGIN_ATTEMPTS:
        locked_until = (datetime.now() + timedelta(minutes=LOCKOUT_DURATION_MINUTES)).isoformat()
        logger.warning(f"Account locked: {username} (too many failed attempts)")

    # Upsert the record
    conn.execute("""
        INSERT INTO login_attempts (username, attempt_count, locked_until, last_attempt)
        VALUES (?, ?, ?, datetime('now','localtime'))
        ON CONFLICT(username) DO UPDATE SET
            attempt_count = ?,
            locked_until = ?,
            last_attempt = datetime('now','localtime')
    """, (username, new_count, locked_until, new_count, locked_until))

    conn.commit()
    conn.close()


def reset_login_attempts(username: str):
    """Reset login attempts after successful login."""
    conn = get_db_connection()
    conn.execute("UPDATE login_attempts SET attempt_count = 0, locked_until = NULL WHERE username = ?", (username,))
    conn.commit()
    conn.close()


def hash_password(password: str) -> str:
    """Hash a password using bcrypt with automatic salt generation."""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against a bcrypt hash."""
    try:
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
    except Exception:
        return False


# Database Helper Functions
def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# User Helpers
def get_user_by_id(user_id):
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return user

def get_user_by_username(username):
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    return user

def verify_user_credentials(username, password):
    """
    Verify user credentials with timing-attack resistance.
    Always performs bcrypt check even if user doesn't exist.
    """
    user = get_user_by_username(username)

    # Dummy hash for timing attack prevention
    # This is a bcrypt hash of "dummy_password_for_timing_attack_prevention"
    dummy_hash = "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyYU5x6RqVQy"

    if user and user['is_active']:
        # User exists, verify actual password
        if verify_password(password, user['password_hash']):
            return user
        return None
    else:
        # User doesn't exist or is inactive, still perform bcrypt check
        # to maintain constant time operation
        verify_password(password, dummy_hash)
        return None

# Auth Decorators
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login', next=request.url))
        
        # Verify user still exists and is active (security check on every request)
        user = get_user_by_id(session['user_id'])
        if not user or not user['is_active']:
            session.clear()
            return redirect(url_for('login'))
            
        # Check if password change required
        if user['force_password_change'] and request.endpoint != 'change_password' and request.endpoint != 'logout':
             return redirect(url_for('change_password'))

        return f(*args, **kwargs)
    return decorated_function

def manager_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login', next=request.url))

        # Verify user still exists and is active (security check)
        user = get_user_by_id(session['user_id'])
        if not user or not user['is_active']:
            session.clear()
            return redirect(url_for('login'))

        if session.get('role') != 'manager':
            # 403 Forbidden for non-managers trying to access admin routes
            return render_template('403.html'), 403

        return f(*args, **kwargs)
    return decorated_function

# Context Processor to inject user into templates
@app.context_processor
def inject_user():
    if 'user_id' in session:
        user = get_user_by_id(session['user_id'])
        return dict(current_user=user)
    return dict(current_user=None)


def allowed_file(filename: str) -> bool:
    """Check if file extension is allowed."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def validate_file_type(file_stream) -> str | None:
    """
    Validate file type using magic bytes (file signature).
    Returns the detected MIME type if valid, 'extension_only' for degraded mode, None otherwise.
    Falls back to extension-only validation if python-magic is not available.
    """
    if not HAS_MAGIC:
        # Degraded mode: extension-only validation
        logger.warning("python-magic not available. File validation is extension-only (degraded mode).")
        return 'extension_only'

    try:
        # Read first 2048 bytes for magic detection
        header = file_stream.read(2048)
        file_stream.seek(0)  # Reset stream position

        mime = magic.Magic(mime=True)
        detected_mime = mime.from_buffer(header)

        # Allow if detected mime is in our allowed keys
        if detected_mime in ALLOWED_MIME_TYPES:
            return detected_mime

        logger.warning(f"Magic rejected mime: {detected_mime}")
        return None
    except Exception as e:
        logger.warning(f"Validation error (falling back to extension check): {e}")
        # Fallback to extension check on error (e.g. missing libmagic)
        return 'extension_only'


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


def redirect_in_house_messages(recipient: str, show_archived: bool):
    params = {}
    if recipient:
        params["recipient"] = recipient
    if show_archived:
        params["show_archived"] = "1"
    return redirect(url_for("in_house_messages_page", **params))


def run_transaction(ops):
    """Execute database operations within a transaction with rollback on error."""
    conn = connect_db()
    try:
        result = ops(conn)
        conn.commit()
        return result
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def verify_manager_password(password: str) -> bool:
    """Verify manager password against DB (checks for any active manager account)."""
    conn = get_db_connection()
    # Check if there is ANY active manager account that matches this password
    # This is a slight simplification: ideally we'd check the CURRENT user if they are a manager,
    # or prompt for a specific manager's credentials. 
    # For this app's scale (likely 1 manager), checking any valid manager credential is acceptable
    # to authorize "manager override" actions.
    managers = conn.execute("SELECT password_hash FROM users WHERE role = 'manager' AND is_active = 1").fetchall()
    conn.close()
    
    for mgr in managers:
        if verify_password(password, mgr['password_hash']):
            return True
            
    return False

# Settings & User Management Routes

# Settings & User Management Routes

@app.get("/settings")
@login_required
def settings_page():
    conn = get_db_connection()
    users = []
    if session.get('role') == 'manager':
        users = conn.execute("SELECT id, username, role, is_active, last_login FROM users ORDER BY username").fetchall()

    conn.close()
    return render_template("settings.html", users=users)

@app.post("/settings/users/add")
@manager_required
@limiter.limit("10 per hour")
def add_user():
    """Create a new user account."""
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '').strip()
    role = request.form.get('role', '').strip()

    # Validate inputs
    if not username or len(username) < 3:
        return redirect(url_for('settings_page', error="Username must be at least 3 characters"))

    if not password or len(password) < 8:
        return redirect(url_for('settings_page', error="Password must be at least 8 characters"))

    if role not in ('manager', 'front_desk', 'night_audit'):
        return redirect(url_for('settings_page', error="Invalid role"))

    # Validate password complexity
    if not re.search(r'[A-Z]', password):
        return redirect(url_for('settings_page', error="Password must contain at least one uppercase letter"))
    if not re.search(r'[a-z]', password):
        return redirect(url_for('settings_page', error="Password must contain at least one lowercase letter"))
    if not re.search(r'[0-9]', password):
        return redirect(url_for('settings_page', error="Password must contain at least one number"))

    # Check username doesn't already exist
    conn = get_db_connection()
    existing = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
    if existing:
        conn.close()
        return redirect(url_for('settings_page', error="Username already exists"))

    # Create user
    hashed = hash_password(password)
    try:
        conn.execute("""
            INSERT INTO users (username, password_hash, role, is_active, force_password_change)
            VALUES (?, ?, ?, 1, 1)
        """, (username, hashed, role))
        conn.commit()
        conn.close()
        return redirect(url_for('settings_page', success=f"User {username} created successfully"))
    except Exception as e:
        conn.close()
        logger.error(f"Error creating user: {e}")
        return redirect(url_for('settings_page', error="Failed to create user"))

# Schedule Routes

@app.get("/schedule")
@login_required
def view_schedule():
    # Calculate start of week (Monday)
    today = date.today()
    
    # Check for week navigation
    week_start_str = request.args.get('week_start')
    if week_start_str:
        try:
            current_week_start = datetime.strptime(week_start_str, "%Y-%m-%d").date()
        except ValueError:
            current_week_start = today - timedelta(days=today.weekday())
    else:
        current_week_start = today - timedelta(days=today.weekday())
        
    prev_week_start = current_week_start - timedelta(days=7)
    next_week_start = current_week_start + timedelta(days=7)
    
    week_dates = []
    for i in range(7):
        week_dates.append(current_week_start + timedelta(days=i))
        
    start_str = week_dates[0].isoformat()
    end_str = week_dates[-1].isoformat()
    
    conn = get_db_connection()
    
    # Fetch schedules
    # Join with users table to get role if linked
    schedules = conn.execute("""
        SELECT s.*, u.username, u.role as user_role 
        FROM schedules s
        LEFT JOIN users u ON s.user_id = u.id
        WHERE s.shift_date BETWEEN ? AND ?
        ORDER BY s.shift_date, s.shift_id
    """, (start_str, end_str)).fetchall()
    
    # Structure data: schedule_data[date_iso][shift_id] = list of assignments
    schedule_data = {d.isoformat(): {1: [], 2: [], 3: []} for d in week_dates}
    
    for s in schedules:
        d = s['shift_date']
        sid = s['shift_id']
        if d in schedule_data and sid in schedule_data[d]:
            # Determine display name and role
            name = s['staff_name']
            if s['username']: # Use linked username if available
                 name = s['username']
            
            # Use override role if set, else user role, else default 'Staff'
            role = s['role']
            if not role and s['user_role']:
                role = s['user_role'].replace('_', ' ').title()
                
            entry = {
                'id': s['id'],
                'name': name,
                'role': role,
                'note': s['note'],
                'user_id': s['user_id']
            }
            schedule_data[d][sid].append(entry)
            
    # Fetch active users for assignment dropdown (Manager only)
    all_users = []
    if session.get('role') == 'manager':
        all_users = conn.execute("SELECT id, username, role FROM users WHERE is_active = 1 ORDER BY username").fetchall()
        
    conn.close()
    
    return render_template(
        "schedule.html",
        week_dates=week_dates,
        current_week_start=current_week_start,
        prev_week_start=prev_week_start,
        next_week_start=next_week_start,
        schedule_data=schedule_data,
        all_users=all_users,
        today_iso=today.isoformat()
    )


@app.post("/schedule/update")
@manager_required
@limiter.limit("100 per hour")
def update_schedule():
    action = request.form.get('action')
    shift_date = request.form.get('shift_date')
    shift_id_raw = request.form.get('shift_id')

    # Validate shift_date format (YYYY-MM-DD)
    try:
        datetime.strptime(shift_date, '%Y-%m-%d')
    except (ValueError, TypeError):
        return redirect(url_for('view_schedule', week_start=request.form.get('week_start')))

    # Validate shift_id is 1, 2, or 3
    try:
        shift_id = int(shift_id_raw)
        if shift_id not in (1, 2, 3):
            return redirect(url_for('view_schedule', week_start=request.form.get('week_start')))
    except (ValueError, TypeError):
        return redirect(url_for('view_schedule', week_start=request.form.get('week_start')))

    conn = get_db_connection()

    if action == 'add':
        user_id_raw = request.form.get('user_id')
        custom_name = request.form.get('custom_name', '').strip()
        role = request.form.get('role', '').strip()
        note = request.form.get('note', '').strip()

        # Limit field lengths
        if len(custom_name) > 100:
            custom_name = custom_name[:100]
        if len(role) > 50:
            role = role[:50]
        if len(note) > 200:
            note = note[:200]

        user_id = int(user_id_raw) if user_id_raw and user_id_raw.isdigit() else None

        staff_name = custom_name
        if user_id:
            # Get username for staff_name backup
            u = conn.execute("SELECT username FROM users WHERE id = ?", (user_id,)).fetchone()
            if u:
                staff_name = u['username']

        if not staff_name:
             conn.close()
             return redirect(url_for('view_schedule', week_start=request.form.get('week_start')))

        try:
            conn.execute("""
                INSERT INTO schedules (user_id, staff_name, shift_date, shift_id, role, note)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, staff_name, shift_date, shift_id, role or None, note or None))
            conn.commit()
        except sqlite3.IntegrityError:
             # Duplicate entry (handled by unique index)
             pass

    elif action == 'remove':
        schedule_id_raw = request.form.get('schedule_id')
        try:
            schedule_id = int(schedule_id_raw)
            conn.execute("DELETE FROM schedules WHERE id = ?", (schedule_id,))
            conn.commit()
        except (ValueError, TypeError):
            pass

    conn.close()

    # Redirect back to the same week
    return redirect(url_for('view_schedule', week_start=request.form.get('week_start')))

# Wake-up Call Routes

@app.get("/wakeup-calls")
@login_required
def wakeup_calls_list():
    today = date.today().isoformat()
    show_all = request.args.get('all') == '1'
    
    conn = get_db_connection()
    if show_all:
         calls = conn.execute("SELECT * FROM wakeup_calls ORDER BY call_date DESC, call_time DESC").fetchall()
    else:
         # Show pending/active calls for today and future
         calls = conn.execute("""
            SELECT * FROM wakeup_calls 
            WHERE status IN ('pending', 'failed') 
            OR (call_date >= ? AND status = 'completed') 
            ORDER BY call_date ASC, call_time ASC
        """, (today,)).fetchall()
    conn.close()
    
    return render_template("wakeup_calls.html", calls=calls, today=today)

@app.post("/wakeup-calls")
@login_required
@limiter.limit("50 per hour")
def add_wakeup_call():
    room_number = request.form.get('room_number', '').strip()
    call_date = request.form.get('call_date')
    call_time = request.form.get('call_time')
    frequency = request.form.get('frequency', 'once')

    # Validate inputs
    if not room_number or not call_date or not call_time:
         return redirect(url_for('wakeup_calls_list', error="Missing fields"))

    # Validate room_number length
    if len(room_number) > 20:
        return redirect(url_for('wakeup_calls_list', error="Room number too long"))

    # Validate date format
    try:
        datetime.strptime(call_date, '%Y-%m-%d')
    except ValueError:
        return redirect(url_for('wakeup_calls_list', error="Invalid date format"))

    # Validate time format (HH:MM)
    try:
        datetime.strptime(call_time, '%H:%M')
    except ValueError:
        return redirect(url_for('wakeup_calls_list', error="Invalid time format"))

    # Validate frequency
    if frequency not in ('once', 'daily'):
        frequency = 'once'

    conn = get_db_connection()
    try:
        conn.execute("""
            INSERT INTO wakeup_calls (room_number, call_date, call_time, frequency, request_source, logged_by_user_id, status)
            VALUES (?, ?, ?, ?, 'desktop', ?, 'pending')
        """, (room_number, call_date, call_time, frequency, session['user_id']))
        conn.commit()
    except Exception as e:
        logger.error(f"Error adding wakeup call: {e}")
        return redirect(url_for('wakeup_calls_list', error="Database error"))
    finally:
        conn.close()

    return redirect(url_for('wakeup_calls_list', success="Call added"))

@app.post("/wakeup-calls/<int:call_id>/update")
@login_required
@limiter.limit("100 per hour")
def update_wakeup_call(call_id):
    status = request.form.get('status')
    outcome_note = request.form.get('outcome_note', '').strip()

    # Validate status
    if status not in ('pending', 'completed', 'failed', 'cancelled'):
        return redirect(url_for('wakeup_calls_list'))

    # Limit outcome_note length
    if len(outcome_note) > 500:
        outcome_note = outcome_note[:500]

    conn = get_db_connection()
    conn.execute("""
        UPDATE wakeup_calls
        SET status = ?, outcome_note = ?, completed_by_user_id = ?, updated_at = ?
        WHERE id = ?
    """, (status, outcome_note, session['user_id'], datetime.now().isoformat(), call_id))
    conn.commit()
    conn.close()

    return redirect(url_for('wakeup_calls_list'))

# Helper for Alerts
def get_due_wakeup_calls():
    """Get wake-up calls due now (within window) or overdue."""
    now = datetime.now()
    today_str = now.date().isoformat()
    time_str = now.strftime("%H:%M")
    
    # Simple check: Date is today. Time is <= now + 10 mins AND status is pending.
    # Also include past pending calls (overdue).
    
    conn = get_db_connection()
    calls = conn.execute("""
        SELECT * FROM wakeup_calls 
        WHERE status = 'pending' 
        AND call_date <= ? 
        ORDER BY call_date ASC, call_time ASC
    """, (today_str,)).fetchall()
    conn.close()
    
    due_calls = []
    for call in calls:
        # Check time
        if call['call_date'] < today_str:
            due_calls.append(call) # Overdue from previous day
            continue
            
        # Parse time
        try:
            c_hour, c_min = map(int, call['call_time'].split(':'))
            call_dt = now.replace(hour=c_hour, minute=c_min, second=0, microsecond=0)
            
            # Due window: 10 mins before to infinity (until handled)
            # "Appears if 10 mins before/after" -> alert logic.
            # But we want to show anything PENDING that is due or past due.
            if call_dt <= now + timedelta(minutes=10):
                due_calls.append(call)
        except ValueError:
            pass
            
    return due_calls

@app.context_processor
def inject_alerts():
    # Only inject if logged in
    if 'user_id' not in session:
        return {}
        
    # Check if this user should see notifications
    # Logic: "Notification Routing"
    # 1. Is user on schedule now?
    # 2. Does user have 'wakeup_calls' preference enabled?
    # If yes to both, show.
    # If no one is on schedule, show to all Front Desk/Night Audit.
    
    # We can't easily calculate "no one is on schedule" cheaply in context processor
    # Simplification: Show to anyone with role Front Desk/Night Audit/Manager who has preference ON.
    # And maybe prioritized if on schedule.
    
    user = get_user_by_id(session['user_id'])
    if not user: 
        return {}

    # Check prefs
    prefs = {}
    if user['notification_preferences']:
        try:
            prefs = json.loads(user['notification_preferences'])
        except:
            pass
            
    if not prefs.get('wakeup_calls', True): # Default True
        return {'wakeup_alert_count': 0}
        
    # Get count
    due_calls = get_due_wakeup_calls()
    return {'wakeup_alert_count': len(due_calls), 'due_wakeup_calls': due_calls}

@app.post("/settings/users/<int:user_id>/reset")
@manager_required
def reset_user_password(user_id):
    new_password = request.form.get('new_password', '').strip()
    if len(new_password) < 8:
         return redirect(url_for('settings_page', error="Password too short"))
         
    hashed = hash_password(new_password)
    
    conn = get_db_connection()
    conn.execute("""
        UPDATE users 
        SET password_hash = ?, force_password_change = 1
        WHERE id = ?
    """, (hashed, user_id))
    conn.commit()
    conn.close()
    
    return redirect(url_for('settings_page', success="Password reset"))

@app.post("/settings/users/<int:user_id>/toggle")
@manager_required
def toggle_user_active(user_id):
    # Prevent deactivating yourself
    if user_id == session['user_id']:
        return redirect(url_for('settings_page', error="Cannot deactivate yourself"))

    conn = get_db_connection()
    user = conn.execute("SELECT is_active FROM users WHERE id = ?", (user_id,)).fetchone()
    if user:
        new_status = 0 if user['is_active'] else 1
        conn.execute("UPDATE users SET is_active = ? WHERE id = ?", (new_status, user_id))
        conn.commit()
    conn.close()
    
    return redirect(url_for('settings_page'))

@app.post("/settings/preferences")
@login_required
def update_preferences():
    wakeup_notifications = request.form.get('wakeup_calls') == 'on'
    
    prefs = {'wakeup_calls': wakeup_notifications}
    
    conn = get_db_connection()
    conn.execute("UPDATE users SET notification_preferences = ? WHERE id = ?", (json.dumps(prefs), session['user_id']))
    conn.commit()
    conn.close()
    
    return redirect(url_for('settings_page', success="Preferences updated"))


# Routes
@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def login():
    # If already logged in, redirect to overview
    if 'user_id' in session:
        return redirect(url_for('overview'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # Check lockout
        if is_account_locked(username):
             return render_template('login.html', error="Account is temporarily locked. Please try again later.")

        user = verify_user_credentials(username, password)

        if user:
            # Success
            reset_login_attempts(username)

            # Regenerate session to prevent session fixation attacks
            # Save next_page before clearing session
            next_page = request.args.get('next')
            session.clear()

            # Set new session data
            session.permanent = True
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']

            # Update last login time
            conn = get_db_connection()
            conn.execute("UPDATE users SET last_login = ? WHERE id = ?", (datetime.now().isoformat(), user['id']))
            conn.commit()
            conn.close()

            # Force password change check
            if user['force_password_change']:
                return redirect(url_for('change_password'))

            return redirect(next_page or url_for('overview'))
        else:
            # Failed
            record_failed_login(username)
            return render_template('login.html', error="Invalid username or password")

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/change-password', methods=['GET', 'POST'])
@login_required
@limiter.limit("10 per hour")
def change_password():
    if request.method == 'POST':
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')

        if new_password != confirm_password:
             return render_template('change_password.html', error="Passwords do not match")

        if len(new_password) < 8:
             return render_template('change_password.html', error="Password must be at least 8 characters")

        # Validate password complexity
        if not re.search(r'[A-Z]', new_password):
            return render_template('change_password.html', error="Password must contain at least one uppercase letter")
        if not re.search(r'[a-z]', new_password):
            return render_template('change_password.html', error="Password must contain at least one lowercase letter")
        if not re.search(r'[0-9]', new_password):
            return render_template('change_password.html', error="Password must contain at least one number")
             
        # Update password
        hashed = hash_password(new_password)
        conn = get_db_connection()
        conn.execute("UPDATE users SET password_hash = ?, force_password_change = 0 WHERE id = ?", (hashed, session['user_id']))
        conn.commit()
        conn.close()
        
        return redirect(url_for('overview'))
        
    return render_template('change_password.html')


def parse_db_timestamp(value: str) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        # Replace space with T for Python 3.10 compatibility (fromisoformat is stricter)
        normalized = value.replace(" ", "T", 1) if " " in value else value
        return datetime.fromisoformat(normalized)
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

    # Make timezone aware if it isn't
    if not created_at.tzinfo:
        created_at = created_at.replace(tzinfo=TIMEZONE)

    shift_id = entry.get("shift_id")
    if not shift_id:
        # Fallback to time-based for old entries without shift_id
        now = datetime.now(TIMEZONE)
        return now - created_at <= timedelta(minutes=LOG_EDIT_WINDOW_MINUTES)

    # Calculate the logical shift date for this entry
    # (e.g. 1AM on Jan 2 is part of Jan 1 Shift 3)
    entry_shift_date = shift_utils.get_shift_date(created_at)

    # Check if this specific shift is still active
    return shift_utils.is_shift_active(shift_id, entry_shift_date)


def is_editable_maintenance_item(item: dict) -> bool:
    created_at = parse_db_timestamp(item.get("created_at"))
    if not created_at:
        return False
    # UX: Maintenance details can only be adjusted shortly after logging.
    # Use timezone-aware datetime for comparison if created_at is timezone-aware
    now = datetime.now(TIMEZONE) if created_at.tzinfo else datetime.now()
    return now - created_at <= timedelta(minutes=MAINTENANCE_EDIT_WINDOW_MINUTES)


def log_entry_summary(title: str, location: str | None) -> str:
    if location:
        return f"{location.strip()} {title.strip()}"
    return title.strip()


def local_timestamp() -> str:
    return datetime.now(TIMEZONE).isoformat(sep=" ", timespec="seconds")


def future_timestamp(days: int) -> str:
    return (datetime.now(TIMEZONE) + timedelta(days=days)).isoformat(sep=" ", timespec="seconds")


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


def generate_service_dates(start_date: date, end_date: date, frequency: str, frequency_days: int | None = None) -> list[str]:
    """
    Generate explicit service dates based on frequency mode.

    Rules:
    - Start from the first full day after check-in (start_date)
    - Exclude checkout day (end_date)
    - Auto-expire all dates at checkout

    Args:
        start_date: First full day of stay
        end_date: Checkout date (excluded from service)
        frequency: 'none', 'every_3rd_day', 'daily', or 'custom'
        frequency_days: Required for 'custom', number of days between service

    Returns:
        List of service dates in ISO format (YYYY-MM-DD)
    """
    if not start_date or not end_date:
        return []

    if frequency == 'none':
        return []

    service_dates = []

    if frequency == 'daily':
        # Every day from start_date to end_date (excluding checkout)
        current = start_date
        while current < end_date:
            service_dates.append(current.isoformat())
            current += timedelta(days=1)

    elif frequency == 'every_3rd_day':
        # Every 3rd day starting from start_date
        current = start_date
        while current < end_date:
            service_dates.append(current.isoformat())
            current += timedelta(days=3)

    elif frequency == 'custom' and frequency_days:
        # Custom interval based on frequency_days
        current = start_date
        while current < end_date:
            service_dates.append(current.isoformat())
            current += timedelta(days=frequency_days)

    return service_dates


def housekeeping_due_today(start_date: date, end_date: date, today: date, frequency_days: int = 3) -> bool:
    if not start_date or not end_date:
        return False
    # Ignore requests before start date or on/after checkout date
    if today < start_date or today >= end_date:
        return False
    # Daily frequency (frequency_days=1) is always due
    if frequency_days == 1:
        return True
    # For other frequencies, check if today is on schedule
    return (today - start_date).days % frequency_days == 0


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
    shift_id=None,
):
    if is_system_event:
        author_name = "System"
    if not author_name:
        raise ValueError("author_name is required for log entries")
    if not created_at:
        created_at = local_timestamp()
    conn = connect_db()
    conn.execute("""
        INSERT INTO log_entries (author_name, note, related_record_id, related_maintenance_id, is_system_event, created_at, shift_id)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (author_name, note, related_record_id, related_maintenance_id, int(is_system_event), created_at, shift_id))
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


def insert_service_dates(request_id: int, service_dates: list[str]):
    """Insert service dates for a housekeeping request."""
    if not service_dates:
        return
    conn = connect_db()
    for service_date in service_dates:
        conn.execute("""
            INSERT INTO housekeeping_service_dates (housekeeping_request_id, service_date, is_active)
            VALUES (?, ?, 1)
        """, (request_id, service_date))
    conn.commit()
    conn.close()


def get_frequency_label(frequency: str, frequency_days: int | None = None) -> str:
    """Get human-readable frequency label for display."""
    if frequency == 'none':
        return 'No Housekeeping'
    elif frequency == 'daily':
        return 'Daily'
    elif frequency == 'every_3rd_day':
        return 'Every 3rd Day'
    elif frequency == 'custom' and frequency_days:
        if frequency_days == 1:
            return 'Daily'
        elif frequency_days == 2:
            return 'Every Other Day'
        else:
            return f'Every {frequency_days} Days'
    return 'Unknown'


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
        "housekeeping_service_dates",
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
        logger.warning(f"Missing tables: {missing_list}")
        logger.warning("Run: python migrate_add_log_maintenance.py")


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



@app.get("/")
@app.get("/overview")
@login_required
def overview():
    conn = get_db_connection()
    
    # 1. Alert Counts
    # Wakeups
    today_str = date.today().isoformat()
    wakeup_alert_count = conn.execute("""
        SELECT COUNT(*) FROM wakeup_calls 
        WHERE call_date = ? AND status = 'pending'
    """, (today_str,)).fetchone()[0]

    # Room Issues
    ooo_count = conn.execute("SELECT COUNT(*) FROM room_issues WHERE status = 'out_of_order' AND state = 'active'").fetchone()[0]
    uin_count = conn.execute("SELECT COUNT(*) FROM room_issues WHERE status = 'use_if_needed' AND state = 'active'").fetchone()[0]
    
    # DNR
    active_dnr_count = conn.execute("SELECT COUNT(*) FROM records WHERE status = 'active'").fetchone()[0]

    # Maintenance (Open)
    open_maintenance_count = conn.execute("SELECT COUNT(*) FROM maintenance_items WHERE status IN ('open', 'in_progress', 'blocked')").fetchone()[0]
    
    # 2. Active Announcements
    now = datetime.now()
    now_str = now.isoformat()
    announcements = conn.execute("""
        SELECT * FROM staff_announcements 
        WHERE is_active = 1 
        AND (starts_at IS NULL OR starts_at <= ?)
        AND (ends_at IS NULL OR ends_at >= ?)
        ORDER BY created_at DESC
    """, (now_str, now_str)).fetchall()
    
    # 3. Recent Activity Feed (Logs)
    # Filter for non-system events if that's what the template expects? 
    # Template calls it 'recent_notes' and iterates.
    recent_notes = conn.execute("""
        SELECT * FROM log_entries 
        WHERE is_system_event = 0
        ORDER BY created_at DESC 
        LIMIT 20
    """).fetchall()
    
    # 4. Shift Schedule (if used, but template doesn't seem to use 'shifts' variable in the section I saw, but let's keep it just in case)
    shifts = conn.execute("""
        SELECT s.*, u.username 
        FROM schedules s
        LEFT JOIN users u ON s.user_id = u.id
        WHERE shift_date = ?
        ORDER BY shift_id
    """, (today_str,)).fetchall()
    
    conn.close()
    
    return render_template(
        "overview.html",
        # Alerts
        wakeup_alert_count=wakeup_alert_count,
        room_out_of_order_count=ooo_count,
        room_use_if_needed_count=uin_count,
        
        # Awareness
        active_dnr_count=active_dnr_count,
        open_maintenance_count=open_maintenance_count,
        
        # Content
        announcements=announcements,
        recent_notes=recent_notes,
        shifts=shifts,
        last_updated=now.strftime("%Y-%m-%d %H:%M:%S")
    )


@app.get("/mobile")
@login_required
def mobile_dashboard():
    todays_date = date.today()
    today_str = todays_date.isoformat()
    
    conn = get_db_connection()
    
    # Fetch today's schedule
    schedules = conn.execute("""
        SELECT s.*, u.username, u.role as user_role 
        FROM schedules s
        LEFT JOIN users u ON s.user_id = u.id
        WHERE s.shift_date = ?
        ORDER BY s.shift_id
    """, (today_str,)).fetchall()
    
    today_schedule = {1: [], 2: [], 3: []}
    for s in schedules:
        name = s['staff_name'] or s['username']
        role = s['role'] or (s['user_role'].replace('_', ' ').title() if s['user_role'] else 'Staff')
        today_schedule[s['shift_id']].append({'name': name, 'role': role})
        
    # Fetch today's wake-up calls
    wakeup_calls = conn.execute("""
        SELECT * FROM wakeup_calls 
        WHERE call_date = ?
        ORDER BY call_time ASC
    """, (today_str,)).fetchall()
    
    conn.close()
    
    return render_template("mobile/dashboard.html", today_schedule=today_schedule, wakeup_calls=wakeup_calls)


@app.get("/")



@app.get("/api/overview-alerts")
@login_required
def get_overview_alerts():
    """Get real-time alert counts for the dashboard poll."""
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

    # Wake-up calls due (same logic as alert helper)
    # Due now (status='pending' AND call_date/time has passed or is within 10 mins)
    # Simplified SQL check for polling
    now = datetime.now()
    today_str = now.date().isoformat()
    # Fetch pending for today/past
    pending_calls = conn.execute("""
        SELECT * FROM wakeup_calls 
        WHERE status = 'pending' 
        AND call_date <= ?
    """, (today_str,)).fetchall()
    
    wakeup_alert_count = 0
    for call in pending_calls:
        if call['call_date'] < today_str:
            wakeup_alert_count += 1
            continue
        try:
            c_hour, c_min = map(int, call['call_time'].split(':'))
            call_dt = now.replace(hour=c_hour, minute=c_min, second=0, microsecond=0)
            if call_dt <= now + timedelta(minutes=10):
                wakeup_alert_count += 1
        except:
            pass
    
    conn.close()

    return jsonify({
        "active_dnr_count": active_dnr_count,
        "room_out_of_order_count": room_out_of_order_count,
        "room_use_if_needed_count": room_use_if_needed_count,
        "open_maintenance_count": open_maintenance_count,
        "wakeup_alert_count": wakeup_alert_count,
        "last_updated": local_timestamp()
    })


@app.get("/log-book")
@login_required
def log_book():
    # Get filter parameters
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()
    shift_filter = request.args.get("shift", "").strip()

    filters = {
        "date_from": date_from,
        "date_to": date_to,
        "shift": shift_filter,
        "has_filters": bool(date_from or date_to or shift_filter),
    }

    # Build query with filters
    sql = "SELECT * FROM log_entries WHERE is_system_event = 0"
    params = []

    if date_from:
        sql += " AND DATE(created_at) >= ?"
        params.append(date_from)

    if date_to:
        sql += " AND DATE(created_at) <= ?"
        params.append(date_to)

    if shift_filter in ("1", "2", "3"):
        sql += " AND shift_id = ?"
        params.append(int(shift_filter))

    sql += " ORDER BY created_at DESC, id DESC"

    conn = connect_db()
    entries = conn.execute(sql, params).fetchall()
    conn.close()

    edit_id = request.args.get("edit", "").strip()
    editable_id = None
    if edit_id.isdigit():
        editable_id = int(edit_id)

    for entry in entries:
        entry["is_editable"] = is_editable_log_entry(entry)

    return render_template("log_book.html", entries=entries, editable_id=editable_id, filters=filters)


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
    staff_name = request.form.get("staff_name", "").strip()[:100]
    shift_id_str = request.form.get("shift_id", "").strip()
    is_mobile = request.form.get("is_mobile") == "1"

    if not note or not staff_name:
        if is_mobile:
            return redirect(url_for("mobile_dashboard", error="Missing note"))
        return redirect(url_for("log_book"))

    shift_id = None
    if shift_id_str in ("1", "2", "3"):
        shift_id = int(shift_id_str)
        
    if is_mobile:
        note += "\n\n(Added via mobile)"

    insert_log_entry(note, author_name=staff_name, is_system_event=False, shift_id=shift_id)

    if is_mobile:
        return redirect(url_for("mobile_dashboard", success="Note added"))
    return redirect(url_for("log_book"))


@app.post("/log-book/entries/<int:entry_id>/edit")
@login_required
@limiter.limit("10 per minute")
def edit_log_entry(entry_id):
    conn = connect_db()
    entry_row = conn.execute("""
        SELECT * FROM log_entries WHERE id = ?
    """, (entry_id,)).fetchone()

    if not entry_row:
        conn.close()
        return redirect(url_for("log_book"))

    entry = dict(entry_row)

    if entry.get("is_system_event"):
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

    return redirect(url_for("log_book"))


@app.post("/log-book/entries/<int:entry_id>/delete")
@login_required
@limiter.limit("10 per minute")
def delete_log_entry(entry_id):
    """Delete a log entry permanently."""
    conn = connect_db()
    entry_row = conn.execute("""
        SELECT * FROM log_entries WHERE id = ?
    """, (entry_id,)).fetchone()

    if not entry_row:
        conn.close()
        return redirect(url_for("log_book"))

    entry = dict(entry_row)

    # Only allow deleting non-system entries
    if entry.get("is_system_event"):
        conn.close()
        return redirect(url_for("log_book"))

    # Check if entry is still editable (within 10-minute window)
    if not is_editable_log_entry(entry):
        conn.close()
        return redirect(url_for("log_book"))

    conn.execute("""
        DELETE FROM log_entries WHERE id = ?
    """, (entry_id,))
    conn.commit()
    conn.close()

    return redirect(url_for("log_book"))


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
    item_row = conn.execute("""
        SELECT * FROM maintenance_items WHERE id = ?
    """, (item_id,)).fetchone()

    if not item_row:
        conn.close()
        return redirect(url_for("maintenance_list"))

    item = dict(item_row)

    if not is_editable_maintenance_item(item):
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
    item_row = conn.execute("""
        SELECT * FROM maintenance_items WHERE id = ?
    """, (item_id,)).fetchone()

    if not item_row:
        conn.close()
        return redirect(url_for("maintenance_list"))

    item = dict(item_row)

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


@app.post("/maintenance/<int:item_id>/delete")
@login_required
@limiter.limit("10 per minute")
def delete_maintenance_item(item_id):
    """Delete a maintenance item permanently."""
    conn = connect_db()
    item_row = conn.execute("""
        SELECT * FROM maintenance_items WHERE id = ?
    """, (item_id,)).fetchone()

    if not item_row:
        conn.close()
        return redirect(url_for("maintenance_list"))

    item = dict(item_row)

    # Check if item is still editable (within 10-minute window)
    if not is_editable_maintenance_item(item):
        conn.close()
        return redirect(url_for("maintenance_list"))

    conn.execute("""
        DELETE FROM maintenance_items WHERE id = ?
    """, (item_id,))
    conn.commit()
    conn.close()

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

    edit_id = request.args.get("edit", "").strip()
    editable_id = int(edit_id) if edit_id.isdigit() else None

    return render_template("room_issues.html", issues=issues, edit_id=editable_id)


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


@app.post("/room-issues/<int:issue_id>/edit")
@login_required
@limiter.limit("10 per minute")
def edit_room_issue(issue_id):
    room_number = request.form.get("room_number", "").strip()[:20]
    status = request.form.get("status", "").strip()
    note = request.form.get("note", "").strip()[:1000]

    if not room_number or status not in {"out_of_order", "use_if_needed"}:
        return redirect(url_for("room_issues_list", edit=issue_id))

    now = local_timestamp()
    conn = connect_db()
    conn.execute("""
        UPDATE room_issues
        SET room_number = ?, status = ?, note = ?, updated_at = ?
        WHERE id = ?
    """, (room_number, status, note or None, now, issue_id))
    conn.commit()
    conn.close()

    return redirect(url_for("room_issues_list"))


@app.post("/room-issues/<int:issue_id>/delete")
@login_required
@limiter.limit("5 per minute")
def delete_room_issue(issue_id):
    conn = connect_db()
    conn.execute("DELETE FROM room_issues WHERE id = ?", (issue_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("room_issues_list"))


@app.get("/housekeeping-requests")
@login_required
def housekeeping_requests():
    today = date.today()
    today_str = today.isoformat()

    # Query ALL active requests (today is between start and checkout)
    conn = connect_db()
    all_active_raw = conn.execute("""
        SELECT * FROM housekeeping_requests
        WHERE date(start_date) <= date(?)
        AND date(end_date) > date(?)
        ORDER BY id DESC
    """, (today_str, today_str)).fetchall()

    # Query expiring requests (checkout today)
    expiring_raw = conn.execute("""
        SELECT * FROM housekeeping_requests
        WHERE date(end_date) = date(?)
        ORDER BY id DESC
    """, (today_str,)).fetchall()
    conn.close()

    # Process all active requests and compute which are due today
    due_today = []
    all_active = []

    for item in all_active_raw:
        item_dict = dict(item)
        item_dict['frequency_label'] = get_frequency_label(item_dict.get('frequency'), item_dict.get('frequency_days'))

        # Compute if due today
        start_date = parse_date_input(item_dict.get('start_date'))
        end_date = parse_date_input(item_dict.get('end_date'))
        frequency = item_dict.get('frequency')
        frequency_days = item_dict.get('frequency_days')

        # Compute frequency_days for non-custom frequencies
        if frequency == 'daily':
            freq_days_computed = 1
        elif frequency == 'every_3rd_day':
            freq_days_computed = 3
        elif frequency == 'custom' and frequency_days:
            freq_days_computed = frequency_days
        else:
            freq_days_computed = 3  # default

        is_due_today = housekeeping_due_today(start_date, end_date, today, freq_days_computed)
        item_dict['is_due_today'] = is_due_today

        if is_due_today:
            due_today.append(item_dict)
        all_active.append(item_dict)

    # Sort both lists by room number
    due_today.sort(key=lambda item: room_sort_key(item.get("room_number", "")))
    all_active.sort(key=lambda item: room_sort_key(item.get("room_number", "")))

    # Process expiring requests
    expiring_today = []
    for item in expiring_raw:
        item_dict = dict(item)
        item_dict['frequency_label'] = get_frequency_label(item_dict.get('frequency'), item_dict.get('frequency_days'))
        expiring_today.append(item_dict)
    
    expiring_today.sort(key=lambda item: room_sort_key(item.get("room_number", "")))

    edit_id = request.args.get("edit", "").strip()
    editable_id = int(edit_id) if edit_id.isdigit() else None
    edit_item = None
    if editable_id:
        conn = connect_db()
        row = conn.execute("SELECT * FROM housekeeping_requests WHERE id = ?", (editable_id,)).fetchone()
        conn.close()
        if row:
            edit_item = dict(row)

    return render_template(
        "housekeeping_requests.html",
        due_today=due_today,
        all_active=all_active,
        expiring_today=expiring_today,
        print_rooms=[
            {
                "room": item.get("room_number", ""),
                "guest": item.get("guest_name", ""),
                "frequency": item.get("frequency_label", ""),
                "notes": item.get("notes", ""),
            }
            for item in due_today
        ],
        edit_item=edit_item,
        today=today_str,
        error=request.args.get("error", "").strip(),
    )


@app.post("/housekeeping-requests")
@login_required
@limiter.limit("10 per minute")
def add_housekeeping_request():
    room_number = request.form.get("room_number", "").strip()[:20]
    guest_name = request.form.get("guest_name", "").strip()[:100]
    start_raw = request.form.get("start_date", "").strip()
    end_raw = request.form.get("end_date", "").strip()
    frequency = request.form.get("frequency", "every_3rd_day").strip()
    if frequency == "none":
        frequency = "every_3rd_day"
        
    frequency_days_raw = request.form.get("frequency_days", "").strip()
    notes = request.form.get("notes", "").strip()[:1000]

    start_date = parse_date_input(start_raw)
    end_date = parse_date_input(end_raw)

    if not room_number or not start_date or not end_date:
        return redirect(url_for("housekeeping_requests", error="missing"))
    if start_date > end_date:
        return redirect(url_for("housekeeping_requests", error="date_order"))

    # Parse frequency_days for custom frequency
    frequency_days = None
    if frequency == "custom":
        try:
            frequency_days = int(frequency_days_raw)
            if frequency_days < 1 or frequency_days > 30:
                return redirect(url_for("housekeeping_requests", error="invalid_frequency"))
        except (ValueError, TypeError):
            return redirect(url_for("housekeeping_requests", error="invalid_frequency"))

    # Generate service dates based on frequency
    service_dates = generate_service_dates(start_date, end_date, frequency, frequency_days)
    now = local_timestamp()

    def create_housekeeping_request(conn):
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO housekeeping_requests (room_number, guest_name, start_date, end_date, frequency, frequency_days, notes, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (room_number, guest_name or None, start_date.isoformat(), end_date.isoformat(), frequency, frequency_days, notes or None, now, now))
        request_id = cursor.lastrowid

        # Insert service dates
        if service_dates:
            for service_date in service_dates:
                conn.execute("""
                    INSERT INTO housekeeping_service_dates (housekeeping_request_id, service_date, is_active)
                    VALUES (?, ?, 1)
                """, (request_id, service_date))

        return request_id

    try:
        run_transaction(create_housekeeping_request)
        return redirect(url_for("housekeeping_requests"))
    except Exception:
        return redirect(url_for("housekeeping_requests", error="db_error"))


@app.post("/housekeeping-requests/<int:request_id>/edit")
@login_required
@limiter.limit("10 per minute")
def edit_housekeeping_request(request_id):
    # Get all editable fields
    room_number = request.form.get("room_number", "").strip()[:20]
    guest_name = request.form.get("guest_name", "").strip()[:100]
    start_raw = request.form.get("start_date", "").strip()
    end_raw = request.form.get("end_date", "").strip()
    frequency = request.form.get("frequency", "").strip()
    frequency_days_raw = request.form.get("frequency_days", "").strip()
    notes = request.form.get("notes", "").strip()[:1000]
    start_date = parse_date_input(start_raw)
    end_date = parse_date_input(end_raw)

    if not room_number or not start_date or not end_date or not frequency:
        return redirect(url_for("housekeeping_requests", edit=request_id, error="missing"))
    if start_date > end_date:
        return redirect(url_for("housekeeping_requests", edit=request_id, error="date_order"))

    # Parse frequency_days for custom frequency
    frequency_days = None
    if frequency == "custom":
        try:
            frequency_days = int(frequency_days_raw)
            if frequency_days < 1 or frequency_days > 30:
                return redirect(url_for("housekeeping_requests", edit=request_id, error="invalid_frequency"))
        except (ValueError, TypeError):
            return redirect(url_for("housekeeping_requests", edit=request_id, error="invalid_frequency"))

    conn = connect_db()
    existing_row = conn.execute("""
        SELECT * FROM housekeeping_requests WHERE id = ?
    """, (request_id,)).fetchone()

    if not existing_row:
        conn.close()
        return redirect(url_for("housekeeping_requests"))

    existing = dict(existing_row)

    # Update the request
    now = local_timestamp()
    conn.execute("""
        UPDATE housekeeping_requests
        SET room_number = ?, guest_name = ?, start_date = ?, end_date = ?, frequency = ?, frequency_days = ?, notes = ?, updated_at = ?, archived_at = NULL
        WHERE id = ?
    """, (room_number, guest_name or None, start_date.isoformat(), end_date.isoformat(), frequency, frequency_days, notes or None, now, request_id))
    conn.commit()

    # Always regenerate service dates to match updated schedule.
    conn.execute("""
        DELETE FROM housekeeping_service_dates
        WHERE housekeeping_request_id = ?
    """, (request_id,))
    service_dates = generate_service_dates(start_date, end_date, frequency, frequency_days)
    for service_date in service_dates:
        conn.execute("""
            INSERT INTO housekeeping_service_dates (housekeeping_request_id, service_date, is_active)
            VALUES (?, ?, 1)
        """, (request_id, service_date))
    conn.commit()

    conn.close()

    # Log the change
    change_bits = []
    if existing.get("room_number") != room_number:
        change_bits.append(f"room {existing.get('room_number')} -> {room_number}")
    if existing.get("guest_name") != guest_name:
        change_bits.append(f"guest name updated")
    if existing.get("start_date") != start_date.isoformat():
        change_bits.append(f"start {existing.get('start_date')} -> {start_date.isoformat()}")
    if existing.get("end_date") != end_date.isoformat():
        change_bits.append(f"end {existing.get('end_date')} -> {end_date.isoformat()}")
    if existing.get("frequency") != frequency:
        change_bits.append("frequency updated")
    if (existing.get("notes") or "") != (notes or ""):
        change_bits.append("notes updated")
    if change_bits:
        note = f"Housekeeping request updated: {', '.join(change_bits)}"
        note += " (service dates recalculated)"
        insert_housekeeping_event(request_id, note)

    return redirect(url_for("housekeeping_requests"))


@app.get("/api/housekeeping-requests/print-today")
@login_required
def housekeeping_requests_print_today():
    """Compute and return today's due housekeeping requests for printing."""
    today = date.today()
    today_str = today.isoformat()

    conn = connect_db()
    all_active_raw = conn.execute("""
        SELECT * FROM housekeeping_requests
        WHERE date(start_date) <= date(?)
        AND date(end_date) > date(?)
        ORDER BY id DESC
    """, (today_str, today_str)).fetchall()
    conn.close()

    due_today = []
    for item in all_active_raw:
        item_dict = dict(item)
        item_dict["frequency_label"] = get_frequency_label(
            item_dict.get("frequency"), item_dict.get("frequency_days")
        )

        start_date = parse_date_input(item_dict.get("start_date"))
        end_date = parse_date_input(item_dict.get("end_date"))
        frequency = item_dict.get("frequency")
        frequency_days = item_dict.get("frequency_days")

        if frequency == "daily":
            freq_days_computed = 1
        elif frequency == "every_3rd_day":
            freq_days_computed = 3
        elif frequency == "custom" and frequency_days:
            freq_days_computed = frequency_days
        else:
            freq_days_computed = 3

        if housekeeping_due_today(start_date, end_date, today, freq_days_computed):
            due_today.append(item_dict)

    due_today.sort(key=lambda item: room_sort_key(item.get("room_number", "")))

    return jsonify(
        {
            "today": today_str,
            "requests": [
                {
                    "room_number": item.get("room_number", ""),
                    "guest_name": item.get("guest_name", "") or "",
                    "frequency_label": item.get("frequency_label", "") or "",
                    "notes": item.get("notes", "") or "",
                }
                for item in due_today
            ],
        }
    )


@app.post("/housekeeping-requests/<int:request_id>/delete")
@login_required
@limiter.limit("10 per minute")
def delete_housekeeping_request(request_id):
    """Delete a housekeeping request permanently."""
    conn = connect_db()

    # Get the request info for logging
    request_row = conn.execute("""
        SELECT * FROM housekeeping_requests WHERE id = ?
    """, (request_id,)).fetchone()

    if request_row:
        request_dict = dict(request_row)
        room_number = request_dict.get('room_number', 'Unknown')

        # Delete service dates first (foreign key constraint)
        conn.execute("""
            DELETE FROM housekeeping_service_dates
            WHERE housekeeping_request_id = ?
        """, (request_id,))

        # Delete events
        conn.execute("""
            DELETE FROM housekeeping_request_events
            WHERE housekeeping_request_id = ?
        """, (request_id,))

        # Delete the request itself
        conn.execute("""
            DELETE FROM housekeeping_requests WHERE id = ?
        """, (request_id,))

        conn.commit()

    conn.close()
    return redirect(url_for("housekeeping_requests"))


@app.post("/housekeeping-requests/<int:request_id>/toggle-date")
@login_required
@limiter.limit("20 per minute")
def toggle_service_date(request_id):
    """Toggle a specific service date on/off."""
    service_date_str = request.form.get("service_date", "").strip()
    is_active = request.form.get("is_active", "1").strip()

    if not service_date_str:
        return redirect(url_for("housekeeping_requests"))

    try:
        is_active_int = int(is_active)
        if is_active_int not in {0, 1}:
            return redirect(url_for("housekeeping_requests"))
    except ValueError:
        return redirect(url_for("housekeeping_requests"))

    conn = connect_db()
    conn.execute("""
        UPDATE housekeeping_service_dates
        SET is_active = ?
        WHERE housekeeping_request_id = ? AND service_date = ?
    """, (is_active_int, request_id, service_date_str))
    conn.commit()
    conn.close()

    return redirect(url_for("housekeeping_requests", edit=request_id))


@app.get("/housekeeping-requests/<int:request_id>/preview")
@login_required
def preview_service_dates(request_id):
    """Get service dates for a request (for preview and editing)."""
    conn = connect_db()
    request_data = conn.execute("""
        SELECT * FROM housekeeping_requests WHERE id = ?
    """, (request_id,)).fetchone()

    if not request_data:
        conn.close()
        return jsonify({"error": "Request not found"}), 404

    service_dates = conn.execute("""
        SELECT service_date, is_active
        FROM housekeeping_service_dates
        WHERE housekeeping_request_id = ?
        ORDER BY service_date ASC
    """, (request_id,)).fetchall()
    conn.close()

    return jsonify({
        "request": dict(request_data),
        "service_dates": [{"date": sd["service_date"], "active": bool(sd["is_active"])} for sd in service_dates]
    })


@app.post("/api/preview-service-dates")
@login_required
@limiter.limit("20 per minute")
def api_preview_service_dates():
    """Preview service dates before saving (for custom frequency)."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid request"}), 400

    start_raw = data.get("start_date", "").strip()
    end_raw = data.get("end_date", "").strip()
    frequency = data.get("frequency", "").strip()
    frequency_days_raw = data.get("frequency_days")

    start_date = parse_date_input(start_raw)
    end_date = parse_date_input(end_raw)

    if not start_date or not end_date:
        return jsonify({"error": "Invalid dates"}), 400

    frequency_days = None
    if frequency == "custom":
        try:
            frequency_days = int(frequency_days_raw)
            if frequency_days < 1 or frequency_days > 30:
                return jsonify({"error": "Invalid frequency"}), 400
        except (ValueError, TypeError):
            return jsonify({"error": "Invalid frequency"}), 400

    service_dates = generate_service_dates(start_date, end_date, frequency, frequency_days)

    return jsonify({
        "service_dates": service_dates,
        "count": len(service_dates)
    })


@app.get("/staff-announcements")
@login_required
def staff_announcements_list():
    conn = connect_db()
    announcements = conn.execute("""
        SELECT * FROM staff_announcements
        ORDER BY created_at DESC, id DESC
    """).fetchall()
    conn.close()

    edit_id = request.args.get("edit", "").strip()
    editable_id = int(edit_id) if edit_id.isdigit() else None

    return render_template(
        "staff_announcements.html",
        announcements=announcements,
        edit_id=editable_id,
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

    if not verify_manager_password(password):
        return redirect(url_for("staff_announcements_list", error="manager"))

    conn = connect_db()
    conn.execute("DELETE FROM staff_announcements WHERE id = ?", (announcement_id,))
    conn.commit()
    conn.close()

    return redirect(url_for("staff_announcements_list"))


@app.post("/staff-announcements/<int:announcement_id>/edit")
@login_required
@limiter.limit("5 per minute")
def edit_staff_announcement(announcement_id):
    password = request.form.get("manager_password", "").strip()
    if not verify_manager_password(password):
        return redirect(url_for("staff_announcements_list", error="manager", edit=announcement_id))

    message = request.form.get("message", "").strip()[:2000]
    starts_at = normalize_datetime_input(request.form.get("starts_at", "").strip())
    ends_at = normalize_datetime_input(request.form.get("ends_at", "").strip())

    if not message:
        return redirect(url_for("staff_announcements_list", edit=announcement_id))

    conn = connect_db()
    conn.execute("""
        UPDATE staff_announcements
        SET message = ?, starts_at = ?, ends_at = ?
        WHERE id = ?
    """, (message, starts_at, ends_at, announcement_id))
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

    edit_id = None
    edit_param = request.args.get("edit", "").strip()
    if edit_param.isdigit():
        edit_id = int(edit_param)

    return render_template(
        "food_local_spots.html",
        spots=spots,
        edit_id=edit_id,
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
    show_archived = request.args.get("show_archived", "").strip() == "1"
    edit_id = request.args.get("edit", "").strip()
    editable_id = int(edit_id) if edit_id.isdigit() else None
    now = local_timestamp()

    conn = connect_db()

    # Auto-archive expired messages
    conn.execute("""
        UPDATE in_house_messages
        SET archived = 1, archived_at = ?
        WHERE expires_at IS NOT NULL
        AND expires_at <= ?
        AND archived = 0
    """, (now, now))
    conn.commit()

    # Fetch messages based on filter
    if recipient:
        if show_archived:
            # Show all messages (active and archived)
            messages = conn.execute("""
                SELECT * FROM in_house_messages
                WHERE recipient_name = ?
                ORDER BY created_at DESC, id DESC
            """, (recipient,)).fetchall()
        else:
            # Show only active (non-archived) messages
            messages = conn.execute("""
                SELECT * FROM in_house_messages
                WHERE recipient_name = ?
                AND archived = 0
                ORDER BY created_at DESC, id DESC
            """, (recipient,)).fetchall()
    else:
        messages = []
    conn.close()

    return render_template(
        "in_house_messages.html",
        recipient=recipient,
        messages=messages,
        show_archived=show_archived,
        edit_id=editable_id,
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
    # Default expiration: 7 days from creation
    expires_at = future_timestamp(IN_HOUSE_MESSAGE_EXPIRY_DAYS)
    conn = connect_db()
    conn.execute("""
        INSERT INTO in_house_messages
        (recipient_name, message_body, author_name, created_at, expires_at, archived)
        VALUES (?, ?, 'System', ?, ?, 0)
    """, (recipient, body, now, expires_at))
    conn.commit()
    conn.close()

    return redirect_in_house_messages(recipient, show_archived=False)


@app.post("/in-house-messages/<int:message_id>/archive")
@login_required
@limiter.limit("10 per minute")
def archive_in_house_message(message_id):
    """Archive a message (no password required)."""
    recipient = request.form.get("recipient", "").strip()[:100]
    show_archived = request.form.get("show_archived", "").strip() == "1"
    now = local_timestamp()

    conn = connect_db()
    conn.execute("""
        UPDATE in_house_messages
        SET archived = 1, archived_at = ?
        WHERE id = ?
    """, (now, message_id))
    conn.commit()
    conn.close()

    return redirect_in_house_messages(recipient, show_archived)


@app.post("/in-house-messages/<int:message_id>/edit")
@login_required
@limiter.limit("10 per minute")
def edit_in_house_message(message_id):
    recipient = request.form.get("recipient", "").strip()[:100]
    show_archived = request.form.get("show_archived", "").strip() == "1"
    body = request.form.get("message_body", "").strip()[:2000]

    if not body:
        return redirect_in_house_messages(recipient, show_archived)

    conn = connect_db()
    message_row = conn.execute(
        "SELECT archived FROM in_house_messages WHERE id = ?",
        (message_id,),
    ).fetchone()
    if not message_row:
        conn.close()
        return redirect_in_house_messages(recipient, show_archived)

    if int(message_row.get("archived") or 0) == 1:
        conn.close()
        return redirect_in_house_messages(recipient, show_archived)

    conn.execute(
        "UPDATE in_house_messages SET message_body = ? WHERE id = ?",
        (body, message_id),
    )
    conn.commit()
    conn.close()

    return redirect_in_house_messages(recipient, show_archived)


@app.post("/in-house-messages/<int:message_id>/delete")
@login_required
@limiter.limit("10 per minute")
def delete_in_house_message(message_id):
    recipient = request.form.get("recipient", "").strip()[:100]
    show_archived = request.form.get("show_archived", "").strip() == "1"

    conn = connect_db()
    conn.execute("DELETE FROM in_house_messages WHERE id = ?", (message_id,))
    conn.commit()
    conn.close()

    return redirect_in_house_messages(recipient, show_archived)


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

    def create_record(conn):
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

        return record_id

    try:
        record_id = run_transaction(create_record)
        return jsonify({"id": record_id, "message": "Record added successfully"}), 201
    except Exception:
        return jsonify({"error": "Failed to create record. Please try again."}), 500


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

    # Validate file content using magic bytes (or extension-only in degraded mode)
    detected_mime = validate_file_type(file.stream)
    if not detected_mime:
        conn.close()
        return jsonify({"error": "Invalid file content. File does not match declared type."}), 400

    # Generate unique filename with correct extension based on MIME type
    ext = file.filename.rsplit('.', 1)[1].lower()
    filename = f"{uuid.uuid4().hex}.{ext}"
    filepath = os.path.join(UPLOAD_FOLDER, filename)

    # Sanitize original filename for storage
    original_name = file.filename[:255] if file.filename else 'unknown'
    today = str(date.today())

    def save_photo(conn):
        file.save(filepath)
        conn.execute("""
            INSERT INTO photos (record_id, filename, original_name, upload_date)
            VALUES (?, ?, ?, ?)
        """, (record_id, filename, original_name, today))

    try:
        run_transaction(save_photo)
        return jsonify({"message": "Photo uploaded successfully"}), 201
    except Exception as e:
        # Clean up file if database operation failed
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
            except:
                pass
        logger.error(f"Upload error: {e}")
        return jsonify({"error": f"Failed to upload: {str(e)}"}), 500


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
    if not verify_manager_password(password):
        # Log failed attempt silently
        today_iso = datetime.now().isoformat()
        today_str = str(date.today())
        ip = request.remote_addr or 'unknown'

        def log_failed_attempt(conn):
            conn.execute("""
                INSERT INTO password_attempts (record_id, attempt_date, ip_address)
                VALUES (?, ?, ?)
            """, (record_id, today_iso, ip))
            conn.execute("""
                INSERT INTO timeline_entries (record_id, entry_date, note, is_system)
                VALUES (?, ?, 'Failed lift attempt logged', 1)
            """, (record_id, today_str))

        try:
            run_transaction(log_failed_attempt)
        except Exception:
            pass  # Silently ignore logging errors

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
    guest_name = record.get('guest_name', 'Unknown')

    # Add timeline entry
    lift_type_display = {
        'manager_override': 'Manager Override',
        'issue_resolved': 'Issue Resolved',
        'error_entry': 'Error Entry'
    }.get(lift_type, lift_type)

    def perform_lift(conn):
        conn.execute("""
            UPDATE records
            SET status = 'lifted',
                lifted_date = ?,
                lifted_type = ?,
                lifted_reason = ?,
                lifted_initials = ?
            WHERE id = ?
        """, (today, lift_type, lift_reason, initials, record_id))
        conn.execute("""
            INSERT INTO timeline_entries (record_id, entry_date, staff_initials, note, is_system)
            VALUES (?, ?, ?, ?, 1)
        """, (record_id, today, "System", f"Ban lifted. Type: {lift_type_display}. Reason: {lift_reason}"))

    try:
        run_transaction(perform_lift)
    except Exception:
        conn.close()
        return jsonify({"error": "Failed to lift ban. Please try again."}), 500

    conn.close()

    insert_log_entry(
        f"DNR removed for {guest_name}. Type: {lift_type_display}.",
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

    filepath = os.path.join(UPLOAD_FOLDER, photo['filename'])

    def remove_photo(conn):
        conn.execute("DELETE FROM photos WHERE id = ?", (photo_id,))
        if os.path.exists(filepath):
            os.remove(filepath)

    try:
        run_transaction(remove_photo)
        return jsonify({"message": "Photo deleted"}), 200
    except Exception:
        return jsonify({"error": "Failed to delete photo. Please try again."}), 500


@app.get("/api/reasons")
@login_required
def get_reasons():
    """Get predefined ban reasons."""
    return jsonify(BAN_REASONS)





@app.get("/important-numbers")
@login_required
def important_numbers_page():
    conn = connect_db()
    numbers = conn.execute("""
        SELECT * FROM important_numbers
        ORDER BY label ASC, id DESC
    """).fetchall()
    conn.close()

    edit_id = request.args.get("edit", "").strip()
    editable_id = int(edit_id) if edit_id.isdigit() else None

    return render_template(
        "important_numbers.html",
        numbers=numbers,
        edit_id=editable_id,
        error=request.args.get("error", "").strip(),
    )


@app.get("/how-to-guides")
@login_required
def how_to_guides_page():
    conn = connect_db()
    # Support backward compatibility by selecting all columns (schema changed)
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
    if not verify_manager_password(password):
        return redirect(url_for("important_numbers_page", error="manager"))

    conn = connect_db()
    conn.execute("DELETE FROM important_numbers WHERE id = ?", (number_id,))
    conn.commit()
    conn.close()

    return redirect(url_for("important_numbers_page"))


@app.post("/important-numbers/<int:number_id>/edit")
@login_required
@limiter.limit("5 per minute")
def edit_important_number(number_id):
    password = request.form.get("manager_password", "").strip()
    if not verify_manager_password(password):
        return redirect(url_for("important_numbers_page", error="manager", edit=number_id))

    label = request.form.get("label", "").strip()[:200]
    phone = request.form.get("phone", "").strip()[:50]
    notes = request.form.get("notes", "").strip()[:1000]

    if not label or not phone:
        return redirect(url_for("important_numbers_page", edit=number_id))

    conn = connect_db()
    conn.execute(
        "UPDATE important_numbers SET label = ?, phone = ?, notes = ? WHERE id = ?",
        (label, phone, notes or None, number_id),
    )
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

    filename_original = file.filename
    if not (filename_original.lower().endswith(".docx") or filename_original.lower().endswith(".pdf")):
        return redirect(url_for("how_to_guides_page", error="file"))

    # Validate file content using magic bytes
    detected_mime = validate_file_type(file.stream)
    if not detected_mime:
        return redirect(url_for("how_to_guides_page", error="file"))

    # Generate unique filename
    ext = filename_original.rsplit('.', 1)[1].lower()
    filename = f"{uuid.uuid4().hex}.{ext}"
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    file.save(filepath)

    title = os.path.splitext(filename_original)[0].strip()[:200]
    body = "See attached document."

    conn = connect_db()
    conn.execute("""
        INSERT INTO how_to_guides (title, body, created_at, filename, original_filename)
        VALUES (?, ?, ?, ?, ?)
    """, (title, body, local_timestamp(), filename, filename_original))
    conn.commit()
    conn.close()

    return redirect(url_for("how_to_guides_page"))


@app.post("/how-to-guides/<int:guide_id>/delete")
@login_required
@limiter.limit("5 per minute")
def delete_how_to_guide(guide_id):
    password = request.form.get("manager_password", "").strip()
    if not verify_manager_password(password):
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


@app.post("/food-local-spots/<int:spot_id>/edit")
@login_required
@limiter.limit("10 per minute")
def edit_food_local_spot(spot_id):
    name = request.form.get("name", "").strip()[:200]
    address = request.form.get("address", "").strip()[:200]
    phone = request.form.get("phone", "").strip()[:50]
    notes = request.form.get("notes", "").strip()[:1000]

    if not name:
        return redirect(url_for("food_local_spots_page"))

    conn = connect_db()
    conn.execute("""
        UPDATE food_local_spots
        SET name = ?, address = ?, phone = ?, notes = ?
        WHERE id = ?
    """, (name, address or None, phone or None, notes or None, spot_id))
    conn.commit()
    conn.close()

    return redirect(url_for("food_local_spots_page"))


@app.post("/food-local-spots/<int:spot_id>/delete")
@login_required
@limiter.limit("5 per minute")
def delete_food_local_spot(spot_id):
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

    filename_original = file.filename
    if not (filename_original.lower().endswith(".docx") or filename_original.lower().endswith(".pdf")):
        return redirect(url_for("cleaning_checklists_page", error="file"))

    # Validate file content using magic bytes
    detected_mime = validate_file_type(file.stream)
    if not detected_mime:
        return redirect(url_for("cleaning_checklists_page", error="file"))

    # Generate unique filename
    ext = filename_original.rsplit('.', 1)[1].lower()
    filename = f"{uuid.uuid4().hex}.{ext}"
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    file.save(filepath)

    title = os.path.splitext(filename_original)[0].strip()[:200]
    
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO checklist_templates (name, description, is_active, filename, original_filename)
        VALUES (?, 'Imported Document', 1, ?, ?)
    """, (title, filename, filename_original))
    template_id = cursor.lastrowid
    
    # Create a placeholder item
    cursor.execute("""
        INSERT INTO checklist_items (template_id, position, item_text)
        VALUES (?, 1, 'See attached document')
    """, (template_id,))
    
    conn.commit()
    conn.close()

    return redirect(url_for("cleaning_checklists_page"))


@app.post("/cleaning-checklists/<int:template_id>/delete")
@login_required
@limiter.limit("5 per minute")
def delete_cleaning_checklist(template_id):
    password = request.form.get("manager_password", "").strip()
    if not verify_manager_password(password):
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
    if not verify_login_password(current_password):
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
    creds = load_credentials()
    if not creds:
        return jsonify({"error": "Configuration error"}), 500

    new_manager_password_hash = hash_password(new_manager_password)
    save_credentials(creds['username'], creds['password_hash'], new_manager_password_hash)

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
    if not verify_login_password(current_password):
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
    creds = load_credentials()
    if not creds:
        return jsonify({"error": "Configuration error"}), 500

    new_password_hash = hash_password(new_password)
    save_credentials(new_username, new_password_hash, creds['manager_password_hash'], increment_session=True)

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
        logger.info(f"[DEV MODE] Database: {DB_PATH}")
        logger.info(f"[DEV MODE] Upload folder: {UPLOAD_FOLDER}")
        logger.warning("[DEV MODE] Debug mode enabled - DO NOT USE IN PRODUCTION")
        warn_if_missing_tables()

    # Only enable debug mode in development
    port = int(os.environ.get("PORT", "5000"))
    app.run(debug=not is_production, host='127.0.0.1', port=port)
