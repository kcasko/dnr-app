"""
Import existing DNR list from PDF data into the database.
Run this script once to populate the database with historical records.
"""
import sqlite3
import json
from datetime import date

DB_PATH = "dnr.db"

# Map PDF reasons to predefined reasons in the app
REASON_MAPPING = {
    "smoking": "Smoking in non smoking room",
    "drugs": "Drug use",
    "rude": "Aggressive or abusive behavior toward staff",
    "disruptive": "Aggressive or abusive behavior toward staff",
    "aggressive": "Aggressive or abusive behavior toward staff",
    "hostile": "Aggressive or abusive behavior toward staff",
    "scam": "Scammer",
    "fraud": "Scammer",
    "stolen card": "Scammer",
    "con artist": "Scammer",
    "liar": "Scammer",
    "cops": "Local police involvement without arrest",
    "police": "Local police involvement without arrest",
    "former employee": "Former employee on bad terms",
    "damage": "Damage under review",
    "trashed": "Damage under review",
    "broke": "Damage under review",
    "destroyed": "Damage under review",
    "ruined linen": "Ruined linnen",
    "blood": "Ruined linnen",
    "stole": "Stole property",
    "animals": "Animals",
    "dog": "Animals",
    "chargeback": "Chargeback or payment dispute pending",
    "no pay": "Chargeback or payment dispute pending",
    "non-payment": "Chargeback or payment dispute pending",
    "left without paying": "Chargeback or payment dispute pending",
    "unsafe": "Housekeeping safety concern",
    "welfare": "Welfare check initiated",
    "inappropriate": "Policy violation warning issued",
    "trespass": "Policy violation warning issued",
    "noise": "Noise complaints multiple incidents",
}

def map_reasons(reason_text):
    """Map free-text reasons to predefined reasons."""
    reason_lower = reason_text.lower()
    mapped = set()

    for keyword, predefined in REASON_MAPPING.items():
        if keyword in reason_lower:
            mapped.add(predefined)

    # Default if nothing matches
    if not mapped:
        mapped.add("Policy violation warning issued")

    return list(mapped)

def parse_date(date_str):
    """Parse date string to YYYY-MM-DD format."""
    if not date_str or date_str == "X" or date_str.startswith("X"):
        return None

    date_str = date_str.strip().replace("X", "").strip()
    if not date_str:
        return None

    # Handle various formats
    try:
        # Format: M/D/YY or MM/DD/YY
        if "/" in date_str:
            parts = date_str.split("/")
            if len(parts) == 3:
                month, day, year = parts
                if len(year) == 2:
                    year = "20" + year
                return f"{year}-{int(month):02d}-{int(day):02d}"
        # Format: MM/DD/YYYY
        if len(date_str) == 10 and date_str[2] == "/" and date_str[5] == "/":
            parts = date_str.split("/")
            return f"{parts[2]}-{parts[0]}-{parts[1]}"
    except:
        pass

    return None

# DNR entries extracted from PDF
DNR_ENTRIES = [
    # Page 1 entries
    ("Abbey Bodin", "Smoking/Drugs ruined linen", None),
    ("Akila Hampton", "Rude to staff", None),
    ("Alexandrea Hampton", "Smoking in room", None),
    ("Alexis Jean", "Smoking in room", None),
    ("Alisha Gill", "Scammer/Stolen card", None),
    ("Antoinne Whitelow", "Disrespectful/Disruptive/Aggressive behavior", "5/1/24"),
    ("Anthony Childress", "Rude to staff", None),
    ("Ashlie Noneman", "Smoking/Drugs", None),
    ("Autumn Cheesebro", "Smoking in room", None),
    ("Bonnie Smith", "Stolen Cards", None),
    ("Brandon Schumaker", "Smoking in Room", "3/30/24"),
    ("Brenda Mills", "Smoking", None),
    ("Brian Thomas", "Drugs/Fraud", None),
    ("Carson Scheider", "Drugs", None),
    ("Carter Daniel", "Smoking", None),
    ("Cedrick Hill", "Drugs/cops", None),
    ("Christine Williams", "Drugs", None),
    ("Christopher Reynolds", "Smoking", None),
    ("Corey Powell", "Drugs/Dog", None),
    ("Dale Mangold", "Smoking", None),
    ("Dana Corbin", "Smoking", None),
    ("Daniel Carter", "Smoking", None),
    ("Danielle Cornell", "Smoking/drugs", None),
    ("Debra Gomez", "Fraud/Smoking", None),
    ("Demaria Smith", "Smoking in room", "4/25/24"),
    ("Destiny Luce", "Animals, Damages", None),
    ("Dondrell Smith", "Smoking/Disruptive", None),
    ("Dora Butler", "Smoking", None),
    ("Else Taylor", "Non-Payment, Smoked in Room, Damage to window screen", None),
    ("Eric Jiran", "Drugs, and other policies broken", None),
    ("Fred Fey", "Smoking, Rude to Staff, Drugs", None),
    ("Jaime Prater", "Smoking", None),
    ("James Coleman", "Drugs", None),
    ("Jason Page", "Rude to staff, ruined linen", "3/10/24"),
    ("Jennifer Ayres", "Cops Called many times", None),
    ("Jessi Ross", "Disruptive/Former Employee", None),
    ("Jessica Gales", "Rude to staff, trashed room, very messy kids", "3/17/24"),
    ("Jeffery Studley", "Rude to staff", "4/14/24"),
    ("Jimmey Martinez", "Smoking/Trashed Room", None),
    ("Jordan Marrow", "Trespassing, harassing staff", None),
    ("Joseph Bates", "No Pay/Rude to Staff", None),
    ("Kandra Crouch", "Too much police involvement; chased down by police in front parking lot", None),
    ("Kareston Tucker", "Smoking", None),
    ("Kathy Wolf", "Disruptive", None),
    ("Keith Lamouriander", "Disruptive", None),
    ("Keonte Smith", "Scammer", None),
    ("Kristina Buck", "Drugs, Former Employee on bad terms", None),
    ("Kyle Mortimore", "Drugs", None),
    ("Kyle Spence", "Smoking", None),
    ("Leeann Gibson", "Rude to Staff", None),
    ("Lisa McEwean", "Dogs/Smoking", None),
    ("Marcus/Mellisa Yarber", "Cops and drama/Rude to staff", None),
    ("McKaylah Donewalk", "Smoking", None),
    ("Melissa Pasos", "Fraud", None),
    ("Melvin Webb", "Smoking", None),
    ("Millie Snyder", "Former Employee - Bad terms", None),
    ("Natalia Robinson", "Trashed Room/Drugs", None),
    ("Nathan Ellswoth", "Deemed Unsafe by Staff", None),
    ("Nathan McDonald", "Destroyed property, smoking in room", None),
    ("Otto Mullins", "Smoking", None),
    ("Ralph Rider", "Inappropriate", "3/30/24"),
    ("Raymone Hayden", "Bloody Towels/Rude to Staff", None),
    ("Reshon Branson", "Stole Linen", None),
    ("Robert/Tiffany Reschner", "Drugs/Trashed Room", None),
    ("Sally Powers", "Disruptive/Violent", None),
    ("Samuel Jones", "Drugs", None),
    ("Sara Eager", "Smoking/Disruptive", None),
    ("Sarah Simpson", "Broke TV", None),
    ("Shamika Jones", "Disruptive", None),

    # Page 2 entries
    ("Shari Hubbard/Troy Soule/Ryan Soule", "Rude to Staff/Disruptive", None),
    ("Shelly Nichols", "Scam Artist", None),
    ("Stephanie Fockler", "Trashed room/front sidewalk/VERY messy", "3/31/24"),
    ("Susan Winkelman", "Smoking in room/rude to staff", None),
    ("Suzatte Henry", "Con Artist", None),
    ("Taliean Taylor", "Smoking", None),
    ("Teresa Haaga", "Drugs/Blood on Sheets", None),
    ("Terrion Banks", "Smoke/Disruptive", "3/29/24"),
    ("Tiffany Tillery", "Disruptive/Cops called", None),
    ("Toni Berry", "Disruptive", "3/24/24"),
    ("Vanisha McComb", "Drugs", None),
    ("Yasmeen Campbell", "Rude to staff/Smoking", "3/25/24"),
    ("Yasmin Craven", "Too many declined cards and canceled reservations", "4/1/24"),

    # New entries (below the line in PDF)
    ("LAZHANE Mobley", "Cut wires in smoke alarm", "5/7/24"),
    ("Catalies Bailey", "Extremely hostile/argumentative with guests and staff", "5/8/24"),
    ("Tom Rand", "Refusal to pay when we asked, blood all over shower curtain", "5/20/24"),
    ("Lisa Franklin", "Left without paying", "5/23/24"),
    ("Desiree Yancey", "Disruptive guest", "5/27/24"),
    ("Jeannette Collins", "Rude to staff/Scammer", "6/5/24"),
    ("Coen Chaffee", "Inappropriate comments to staff", "6/6/24"),
    ("Lamarco Williams", "Ruined linens, possible smoking", "6/16/24"),
    ("Danielle Morey", "Ruined linens", "6/21/24"),
    ("Jessi Farman", "Drugs", "6/28/24"),
    ("Destiney Bradley", "Hostile with staff", "7/3/24"),
    ("Lacreesha Stanford", "Threw trash in parking lot", "7/3/24"),
    ("Burris Earl", "Makes staff very uncomfortable, deemed unsafe", "7/5/24"),
    ("Andrew Goldberg", "Smoking drugs and setting off the fire alarms", "7/15/24"),
    ("Marvin Harris", "Left without paying for his room", None),
    ("Micheal Spencer", "Smoking found ashes", None),
    ("Tyman Jenkins", "Stolen credit card/police involved", "7/25/24"),
    ("Brooke Cooper", "Chargeback on card/attitude with staff", "8/2/24"),
    ("Jennifer Perry", "Fighting/drugs/stealing", "8/2/24"),
    ("William Robinson", "Domestic Abuse in front of children, 2 arrests at hotel, father drama", "1/25/25"),
    ("Ralph Rider", "Repeat offender", "3/1/25"),
    ("Laura Stacey", "DNR", "3/10/25"),
    ("Alisa Salinaz", "Liar, scammer, drama", "3/15/25"),
    ("Takia Willis-Bowie", "Blood on sheets, poop, kept deposit", "4/9/25"),
    ("Randy Graham", "Room condition severely poor", "4/1/25"),
    ("Paul Schippers", "Leaving animals in truck in 80+ degree weather", "4/24/25"),
    ("Vincent Staffroni", "Staff safety concern", "5/13/25"),
    ("Lakeeta Hall", "Scammer, complains every time to get points", "5/21/25"),
    ("Jontae Washington", "Cigarette butt filled toilet", None),
    ("Brenna King", "Keeps calling about deposit, contacted choice too", "6/12/25"),
    ("Damian Smith", "NO TRESPASS", "6/15/25"),
    ("Darrien Lutz", "Alleged gun on premises, lawsuit drama", "6/18/25"),
]

def import_records():
    """Import all DNR records into the database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    today = str(date.today())
    imported = 0
    skipped = 0

    for name, reason_text, incident_date in DNR_ENTRIES:
        # Check if record already exists
        existing = cursor.execute(
            "SELECT id FROM records WHERE guest_name = ?", (name,)
        ).fetchone()

        if existing:
            print(f"  Skipped (exists): {name}")
            skipped += 1
            continue

        # Map reasons
        reasons = map_reasons(reason_text)
        reasons_json = json.dumps(reasons)

        # Parse incident date
        parsed_date = parse_date(incident_date) if incident_date else None

        # Insert record
        cursor.execute("""
            INSERT INTO records
            (guest_name, status, ban_type, reasons, reason_detail, date_added, incident_date)
            VALUES (?, 'active', 'permanent', ?, ?, ?, ?)
        """, (name, reasons_json, reason_text, today, parsed_date))

        record_id = cursor.lastrowid

        # Add timeline entry
        cursor.execute("""
            INSERT INTO timeline_entries (record_id, entry_date, staff_initials, note, is_system)
            VALUES (?, ?, 'IMP', 'Imported from legacy DNR list. Original reason: ' || ?, 1)
        """, (record_id, today, reason_text))

        print(f"  Imported: {name}")
        imported += 1

    conn.commit()
    conn.close()

    print(f"\n=== Import Complete ===")
    print(f"Imported: {imported}")
    print(f"Skipped (already exist): {skipped}")
    print(f"Total entries: {len(DNR_ENTRIES)}")

if __name__ == "__main__":
    print("Starting DNR list import...")
    print(f"Database: {DB_PATH}")
    print()
    import_records()
