import os
import sqlite3
from flask import Flask, request, jsonify, render_template, redirect, url_for
from datetime import date

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "dnr.db")

app = Flask(__name__)

def dict_factory(cursor, row):
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}

def connect_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = dict_factory
    return conn

@app.get("/")
def home():
    return render_template("index.html")

@app.get("/search")
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
def add_form():
    return render_template("add.html")

@app.post("/add")
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

@app.post("/resolve/<int:incident_id>")
def resolve_incident(incident_id):
    conn = connect_db()
    conn.execute("""
        UPDATE incidents
        SET active = 0,
            expires_on = ?
        WHERE id = ?;
    """, (str(date.today()), incident_id))
    conn.commit()
    conn.close()

    return redirect(url_for("home"))

if __name__ == "__main__":
    print("Using DB:", DB_PATH)
    app.run(debug=True)
