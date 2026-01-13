"""
Restricted Guests Log (Do Not Rent System)
Internal staff reference system for hotel guest bans.
"""
import os
import sqlite3
import hashlib
import uuid
from datetime import date, datetime
from flask import Flask, request, jsonify, render_template, send_from_directory

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "dnr.db")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")

# Ensure upload folder exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload

# Manager password - hashed (default: "manager123" - change in production)
# To generate a new hash: hashlib.sha256("your_password".encode()).hexdigest()
MANAGER_PASSWORD_HASH = hashlib.sha256("manager123".encode()).hexdigest()

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

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
    "Welfare check initiated"
]


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def dict_factory(cursor, row):
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}


def connect_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = dict_factory
    return conn


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


# Routes

@app.get("/")
def home():
    check_expired_bans()
    return render_template("index.html", reasons=BAN_REASONS)


@app.get("/api/records")
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

    sql += " ORDER BY date_added DESC"

    conn = connect_db()
    records = conn.execute(sql, params).fetchall()
    conn.close()

    return jsonify(records)


@app.get("/api/records/<int:record_id>")
def get_record(record_id):
    """Get a single record with timeline and photos."""
    conn = connect_db()

    record = conn.execute(
        "SELECT * FROM records WHERE id = ?", (record_id,)
    ).fetchone()

    if not record:
        conn.close()
        return jsonify({"error": "Record not found"}), 404

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
def add_record():
    """Add a new ban record."""
    data = request.json

    guest_name = data.get('guest_name', '').strip()
    ban_type = data.get('ban_type', '').strip()
    reason = data.get('reason', '').strip()
    reason_detail = data.get('reason_detail', '').strip()
    staff_initials = data.get('staff_initials', '').strip()
    expiration_type = data.get('expiration_type', '')
    expiration_date = data.get('expiration_date', '')

    # Validation
    if not guest_name:
        return jsonify({"error": "Guest name is required"}), 400
    if ban_type not in ('temporary', 'permanent'):
        return jsonify({"error": "Invalid ban type"}), 400
    if not reason:
        return jsonify({"error": "Reason is required"}), 400
    if not staff_initials:
        return jsonify({"error": "Staff initials are required"}), 400

    # For temporary bans, require expiration type
    if ban_type == 'temporary' and not expiration_type:
        return jsonify({"error": "Expiration type required for temporary bans"}), 400

    # For date-based expiration, require date
    if expiration_type == 'date' and not expiration_date:
        return jsonify({"error": "Expiration date required"}), 400

    today = str(date.today())

    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO records
        (guest_name, status, ban_type, reason, reason_detail, date_added,
         expiration_type, expiration_date)
        VALUES (?, 'active', ?, ?, ?, ?, ?, ?)
    """, (guest_name, ban_type, reason, reason_detail or None, today,
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
    staff_initials = data.get('staff_initials', '').strip()
    note = data.get('note', '').strip()

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

    # Generate unique filename
    ext = file.filename.rsplit('.', 1)[1].lower()
    filename = f"{uuid.uuid4().hex}.{ext}"
    filepath = os.path.join(UPLOAD_FOLDER, filename)

    file.save(filepath)

    today = str(date.today())

    conn.execute("""
        INSERT INTO photos (record_id, filename, original_name, upload_date)
        VALUES (?, ?, ?, ?)
    """, (record_id, filename, file.filename, today))

    conn.commit()
    conn.close()

    return jsonify({"message": "Photo uploaded successfully"}), 201


@app.get("/uploads/<filename>")
def serve_upload(filename):
    """Serve uploaded photos."""
    return send_from_directory(UPLOAD_FOLDER, filename)


@app.post("/api/records/<int:record_id>/lift")
def lift_ban(record_id):
    """Lift a ban (requires manager password)."""
    data = request.json

    password = data.get('password', '')
    lift_type = data.get('lift_type', '').strip()
    lift_reason = data.get('lift_reason', '').strip()
    initials = data.get('initials', '').strip()

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

    # Verify password
    password_hash = hashlib.sha256(password.encode()).hexdigest()

    if password_hash != MANAGER_PASSWORD_HASH:
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
def get_reasons():
    """Get predefined ban reasons."""
    return jsonify(BAN_REASONS)


if __name__ == "__main__":
    print(f"Using DB: {DB_PATH}")
    print(f"Upload folder: {UPLOAD_FOLDER}")
    app.run(debug=True)
