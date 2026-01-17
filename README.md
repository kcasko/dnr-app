# Restricted Guests Log (DNR System)

Internal "Do Not Rent" system for hotel staff. Tracks banned guests, reasons, timelines, and photo evidence.

## Tech Stack
- Backend: Flask, SQLite
- Security: bcrypt, Flask-WTF (CSRF), Flask-Limiter
- Frontend: HTML/CSS/JS (no build tooling)

## Project Layout
- `app.py` - Main Flask app (routes, security, DB access)
- `init_db.py` - Creates/reset SQLite schema (development only)
- `migrate.py` - Safe production migration runner
- `import_dnr_list.py` - One-time import of legacy DNR list
- `normalize_names.py` - Title-case normalization for guest names
- `templates/` - Jinja templates (UI and inline JS)
- `static/` - Styles and assets
- `uploads/` - Stored photo evidence
- `dnr.db` - SQLite database
- `.env.example` - Environment variable template

## Setup (Development)
1) Create `.env` from `.env.example` and set `SECRET_KEY`.
2) Create the database schema:

```bash
python init_db.py
```

3) (Optional) Import legacy records:

```bash
python import_dnr_list.py
```

4) Run the app:

```bash
python app.py
```

The app runs on `127.0.0.1` in development.

## Production Migration Workflow
Production data must never be deleted or recreated.

```bash
python migrate.py
```

Run this after pulling new code and before restarting the app. Never run `init_db.py` in production.

## Environment Variables
- `SECRET_KEY` - Required for session encryption.
- `FLASK_ENV` - `development` or `production`.

## Database Schema
Created by `init_db.py` (dev only):
- `records` - main DNR records (status, ban_type, reasons, dates)
- `timeline_entries` - per-record notes and system events
- `photos` - photo evidence metadata
- `password_attempts` - failed lift attempts

Added via `migrate.py` (production-safe):
- `schema_version` - schema version tracker
- `log_entries` - log book entries
- `maintenance_items` - maintenance list

## Core Features
- Login + one-time setup with separate manager password
- Record creation with multiple reasons and optional expiration
- Auto-expire temporary bans by date
- Timeline notes per record
- Photo upload (max 5 per record)
- Lift ban with manager password + audit trail
- Filters, search, and sorting

## Security Notes
- Passwords are bcrypt hashed.
- CSRF tokens required for API calls.
- Rate limits on auth and sensitive endpoints.
- Content Security Policy and security headers enforced.

## Known Legacy/Notes
- `add_sample.py` references a legacy `incidents` table not in the current schema.
- `static/script.js` is unused (JS is inline in `templates/index.html`).

## Useful Commands
List dependencies:

```bash
pip install -r requirements.txt
```

Production-safe migration:

```bash
python migrate.py
```

Add new Log Book and Maintenance tables without wiping data (legacy helper):

```bash
python migrate_add_log_maintenance.py
```

Normalize names:

```bash
python normalize_names.py
```
