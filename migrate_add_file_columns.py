"""
Migration: Add filename columns to how_to_guides and checklist_templates tables.
"""
import sqlite3

DB_PATH = "dnr.db"

def column_exists(cursor, table: str, column: str) -> bool:
    cursor.execute(f"PRAGMA table_info({table})")
    columns = [row[1] for row in cursor.fetchall()]
    return column in columns

def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # how_to_guides
    if not column_exists(cursor, "how_to_guides", "filename"):
        cursor.execute("ALTER TABLE how_to_guides ADD COLUMN filename TEXT")
        print("Added filename to how_to_guides")
    if not column_exists(cursor, "how_to_guides", "original_filename"):
        cursor.execute("ALTER TABLE how_to_guides ADD COLUMN original_filename TEXT")
        print("Added original_filename to how_to_guides")

    # checklist_templates
    if not column_exists(cursor, "checklist_templates", "filename"):
        cursor.execute("ALTER TABLE checklist_templates ADD COLUMN filename TEXT")
        print("Added filename to checklist_templates")
    if not column_exists(cursor, "checklist_templates", "original_filename"):
        cursor.execute("ALTER TABLE checklist_templates ADD COLUMN original_filename TEXT")
        print("Added original_filename to checklist_templates")

    conn.commit()
    conn.close()
    print("Migration complete")

if __name__ == "__main__":
    main()
