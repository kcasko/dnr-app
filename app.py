import os
import sqlite3
import csv
from io import StringIO
from flask import Flask, request, jsonify, render_template, redirect, url_for, session, response
from datetime import date

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "dnr.db")

app = Flask(__name__)

app.secret_key = "dev-secret-change-later"

STAFF_PASSWORD = "staff123"
MANAGER_PASSWORD = "manager123"

def require_login(level="staff"):
    def decorator(fn):
        def wrapper(*args, **kwargs):
            role = session.get("role")
            if not role:
                return redirect(url_for("login"))

            if level == "manager" and role != "manager":
                return "Manager access required", 403

            return fn(*args, **kwargs)
        wrapper.__name__ = fn.__name__
        return wrapper
    return decorator

def dict_factory(cursor, row):
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}

def connect_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = dict_factory
    return conn

@app.get("/login")
def login():
    return render_template("login.html")

@app.post("/login")
def login_post():
    password = request.form.get("password", "")

    if password == STAFF_PASSWORD:
        session["role"] = "staff"
    elif password == MANAGER_PASSWORD:
        session["role"] = "manager"
    else:
        return "Invalid password", 403

    return redirect(url_for("home"))

@app.get("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.get("/")
@require_login()
def home():
    return render_template("index.html")

@app.get("/search")
@require_login()
def search():
    q = (request.args.get("q") or "").strip()

    if not q:
        return jsonify([])

    terms = [t.lower() for t in q.split() if t]

    conditions = []
    params = []

    for term in terms:
        conditions.append(
            "(lower(first_name) LIKE ? OR lower(last_name) LIKE ?)"
        )
        like = f"%{term}%"
        params.extend([like, like])

    where_clause = " AND ".join(conditions)

    sql = f"""
        SELECT *
        FROM incidents
        WHERE active = 1
          AND {where_clause}
        ORDER BY last_name, first_name, incident_date DESC;
    """

    conn = connect_db()
    rows = conn.execute(sql, params).fetchall()
    conn.close()

    return jsonify(rows)

@app.get("/add")
@require_login()
def add_form():
    return render_template("add.html")

@app.post("/add")
@require_login()
def add_incident():
    data = request.form

    first_name = data.get("first_name", "").strip()
    last_name = data.get("last_name", "").strip()
    room_number = data.get("room_number", "").strip()
    reason = data.get("reason", "").strip()
    description = data.get("description", "").strip()
    staff_initials = data.get("staff_initials", "").strip()
    ban_type = data.get("ban_type")

    # Basic validation
    if not all([first_name, last_name, reason, description, staff_initials, ban_type]):
        return "Missing required fields", 400

    incident_date = str(date.today())
    expires_on = None  # unresolved by default
    active = 1

    conn = connect_db()
    conn.execute("""
        INSERT INTO incidents
        (first_name, last_name, incident_date, room_number, reason,
         description, staff_initials, ban_type, expires_on, active)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, (
        first_name,
        last_name,
        incident_date,
        room_number,
        reason,
        description,
        staff_initials,
        ban_type,
        expires_on,
        active
    ))
    conn.commit()
    conn.close()

    return redirect(url_for("home"))

@app.route("/resolve/<int:incident_id>", methods=["GET", "POST"])
@require_login("manager")
def resolve_incident(incident_id):
    conn = connect_db()

    incident = conn.execute("""
        SELECT *
        FROM incidents
        WHERE id = ?;
    """, (incident_id,)).fetchone()

    if not incident:
        conn.close()
        return "Incident not found", 404

    if incident["active"] != 1:
        conn.close()
        return "Incident already resolved", 400

    if incident["ban_type"] != "temporary" or incident["reason"] != "nonpayment":
        conn.close()
        return "Resolution not permitted for this incident", 403

    if request.method == "GET":
        conn.close()
        return render_template("resolve.html", r=incident)

    # POST
    note = request.form.get("resolve_note", "").strip()
    if not note:
        conn.close()
        return "Resolution note required", 400

    conn.execute("""
        UPDATE incidents
        SET active = 0,
            expires_on = ?,
            resolve_note = ?
        WHERE id = ?;
    """, (str(date.today()), note, incident_id))

    conn.commit()
    conn.close()

    return redirect(url_for("home"))

@app.get("/history")
@require_login("manager")
def history():
    conn = connect_db()

    rows = conn.execute("""
        SELECT *
        FROM incidents
        WHERE active = 0
        ORDER BY expires_on DESC, incident_date DESC;
    """).fetchall()

    conn.close()

    return render_template("history.html", incidents=rows)

@app.get("/export.csv")
@require_login("manager")
def export_csv():
    conn = connect_db()

    rows = conn.execute("""
        SELECT
            id,
            first_name,
            last_name,
            incident_date,
            room_number,
            reason,
            description,
            staff_initials,
            ban_type,
            active,
            expires_on,
            resolve_note
        FROM incidents
        ORDER BY active DESC, incident_date DESC;
    """).fetchall()

    conn.close()

    output = StringIO()
    writer = csv.writer(output)

    # Header row
    writer.writerow([
        "ID",
        "First Name",
        "Last Name",
        "Incident Date",
        "Room Number",
        "Reason",
        "Description",
        "Staff Initials",
        "Ban Type",
        "Active",
        "Resolved On",
        "Resolve Note"
    ])

    for r in rows:
        writer.writerow([
            r["id"],
            r["first_name"],
            r["last_name"],
            r["incident_date"],
            r["room_number"],
            r["reason"],
            r["description"],
            r["staff_initials"],
            r["ban_type"],
            "Yes" if r["active"] else "No",
            r["expires_on"] or "",
            r["resolve_note"] or ""
        ])

    output.seek(0)

    return Response(
        output,
        mimetype="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=guest_incidents.csv"
        }
    )

if __name__ == "__main__":
    print("Using DB:", DB_PATH)
    app.run(debug=True)
