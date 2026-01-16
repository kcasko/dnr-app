import sqlite3

DB_PATH = "dnr.db"

def normalize_name(name: str) -> str:
    return " ".join(name.strip().split()).title()

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

rows = cur.execute("SELECT id, guest_name FROM records").fetchall()

for record_id, name in rows:
    fixed = normalize_name(name)
    if fixed != name:
        cur.execute(
            "UPDATE records SET guest_name = ? WHERE id = ?",
            (fixed, record_id)
        )

conn.commit()
conn.close()

print("Name normalization complete.")
