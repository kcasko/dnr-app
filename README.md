# Shift Dashboard - Sleep Inn

Internal "Do Not Rent" (DNR) system for hotel staff management. Tracks banned guests, restricted lists, maintenance issues, and shift logs.

## Features
- **DNR Management**: Track banned guests with reasons, photos, and expiration dates.
- **Operations Dashboard**: Real-time overview of occupancy, issues, and alerts.
- **Shift Handover**: Digital log book for shift notes and staff announcements.
- **Maintenance Tracking**: Ticket system for room and facility repairs.
- **Housekeeping**: Special request tracking and deep clean checklists.
- **Secure Access**: Role-based access with separate manager authorization for sensitive actions.

## Tech Stack
- **Backend**: Python 3.x, Flask
- **Database**: SQLite (local filesystem)
- **Frontend**: HTML5, CSS3 (Custom Design System), Vanilla JavaScript
- **Security**: BCrypt hashing, CSRF protection, Session management

## Project Layout
- `app.py`: Core application logic and routes
- `dnr.db`: SQLite database file
- `templates/`: Jinja2 HTML templates
- `static/`: CSS and asset files
  - `styles.css`: Core design system
- `uploads/`: Photo evidence storage
- `init_db.py`: Database initialization script (Dev only)

## Setup & Installation

1. **Environment Setup**:
   Copy `.env.example` to `.env` and configure your secret key:
   ```bash
   cp .env.example .env
   ```

2. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Initialize Database** (First time only):
   ```bash
   python init_db.py
   ```

4. **Run Application**:
   ```bash
   python app.py
   ```
   Access the app at `http://localhost:5000`

## Production Notes
- This application allows for hot-reloads in development via Flask debug mode.
- In production, ensure the `SECRET_KEY` is strong and kept private.
- Regular backups of `dnr.db` and `uploads/` are recommended.

