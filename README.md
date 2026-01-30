# Front Desk HQ by TaurusTech

## Overview

Front Desk HQ by TaurusTech is an internal hotel front desk operations platform designed to reduce shift friction, missed handoffs, and operational errors in real-world hotel environments.

It is **not** a Property Management System (PMS) and does **not** attempt to replace one. Instead, Front Desk HQ functions as the **missing front desk brain** that operates alongside existing PMS tools.

This product is built for live hotel shifts, interrupted workflows, and small teams who need calm, reliable visibility rather than complex automation.

---

## What This Product Is

Front Desk HQ is:

* A desktop-first operational command center
* A shared memory for shift-to-shift continuity
* A visibility layer for issues, requests, and accountability
* A calm, audit-safe internal tool

Front Desk HQ prioritizes:

* Explicit state over assumptions
* Human confirmation over automation
* Clarity over cleverness
* Trust over surveillance

---

## What This Product Is Not

Front Desk HQ is **not**:

* A PMS replacement
* A booking engine
* A payroll or HR system
* A scheduling enforcement tool
* A messaging or chat platform
* An AI decision-maker
* A surveillance or performance-tracking system

---

## Target Environment

* Small hotel property
* 4–5 active users
* Front desk–centric workflows
* Desktop usage during shifts
* Optional mobile companion for awareness

---

## PROJECT SCOPE (LOCKED)

This scope is authoritative. Any implementation, feature, or design decision must adhere to the constraints below.

---

## Core Design Principles

* Desktop is the **system of record**
* Mobile is **awareness and light notes only**
* No silent automation
* No assumed responsibility
* No background anxiety
* Audit-safe by default
* Scope restraint is a feature

---

## User Model

### Roles (Fixed)

* Front Desk
* Night Audit

---

## Database Migrations

Run the unified upgrade script to bring an existing `dnr.db` up to the current schema:

```
python upgrade_db.py
```

All legacy one-off `migrate_*.py` scripts have been removed in favor of this single, idempotent upgrader.

Roles are:

* Assigned per shift
* Used only for notification targeting and labeling
* Not permissions
* Not hierarchy
* Not HR constructs

### Housekeeping

* Appears in Schedule for visibility only
* No login
* No notifications
* No interaction with the system

### Manager Account

* Exactly one manager account
* Cannot be deactivated
* Manages users, schedules, and global settings
* Admin UI is completely invisible to non-manager users

---

## Authentication & Access

* Individual user accounts required
* No self-signup
* Manager creates and deactivates users
* Manager issues temporary passwords
* Users must change temp passwords on first login
* Users may change passwords anytime
* Passwords are hashed
* No impersonation
* No shared mobile accounts

---

## Included Features (V1)

### Overview / Shift Dashboard

* Clear **Attention Needed → Awareness** hierarchy
* Displays only actionable or relevant items
* No future clutter or passive anxiety

### Do Not Rent (DNR)

* Search, filter, and status tracking
* Explicit records
* Audit-safe behavior

### Shift Notes / Logbook

* Timestamped entries
* Authored entries
* Locked edits after short window
* No retroactive rewriting

### Housekeeping Requests

* Today vs All Active views
* Due indicators
* Print-friendly output
* History preserved

### Room Issues / Maintenance

* Explicit state
* Manual resolution
* Clear visibility

### Schedule

* Current week only
* Visibility-first
* Manager edits only
* Optional informational notes
* Notes do not imply coverage or approval

### Wake-Up Calls

* Created on desktop only
* Manually executed by staff
* Explicit outcomes
* Due-window awareness
* Appears in Attention Needed only when due

---

## Mobile Companion (Scoped)

The mobile app exists to support awareness, not authority.

Mobile can:

* Receive wake-up call notifications
* View current week schedule
* View wake-up calls (read-only)
* Add informational notes

Mobile cannot:

* Resolve wake-up calls
* Edit schedules
* Change room or DNR state
* Perform admin actions
* Become the system of record

All mobile-added notes are clearly labeled.

---

## Notifications

* Awareness only
* Triggered only by wake-up calls entering due window
* Sent only to:

  * Active users
  * Scheduled on current shift
  * Front Desk or Night Audit roles
  * Users with notifications enabled
* No escalation
* No implied responsibility
* Desktop Attention Needed remains fallback

---

## Data & Audit Philosophy

* Explicit timestamps
* Clear attribution
* No silent edits
* Historical records preserved
* Deactivated users remain visible in history
* No surveillance metrics
* No performance scoring

---

## Explicitly Out of Scope

* PMS replacement or integration
* Payroll, HR, or compliance tools
* Shift swapping or approvals
* Auto-executed wake-up calls
* Escalation ladders
* Chat or messaging systems
* AI-driven decisions
* SaaS billing or tenant self-signup

---

## Deployment Strategy

* Single-property deployment
* Single-tenant architecture
* SaaS-ready but **not SaaS**
* No billing flows
* No marketing onboarding
* Real usage before distribution

---

## Future Positioning (Reference Only)

Front Desk HQ may evolve into a sellable product after:

* Proven repeatable use
* Clear external demand
* Intentional SaaS conversion

This does not affect current scope.

---

## Final Enforcement Rule

If a proposed change:

* Adds obligation
* Adds hidden automation
* Adds ambiguity
* Adds stress to staff
* Or expands scope without reducing friction

It is rejected by default.

---

## Tech Stack

* **Backend**: Python 3.x, Flask
* **Database**: SQLite (local filesystem)
* **Frontend**: HTML5, CSS3 (Custom Design System), Vanilla JavaScript
* **Security**: BCrypt hashing, CSRF protection, Session management

## Project Layout

* `app.py`: Core application logic and routes
* `dnr.db`: SQLite database file
* `templates/`: Jinja2 HTML templates
* `static/`: CSS and asset files
  * `styles.css`: Core design system
* `uploads/`: Photo evidence storage
* `init_db.py`: Database initialization script (Dev only)

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

* This application allows for hot-reloads in development via Flask debug mode.
* In production, ensure the `SECRET_KEY` is strong and kept private.
* Regular backups of `dnr.db` and `uploads/` are recommended.
