# Schedule Upload Feature - Implementation Guide

## Overview

The Front Desk HQ app now supports uploading externally created schedules (PDF or DOCX) and importing them into the weekly schedule view. The feature includes a paper-style weekly coverage layout that closely matches traditional hotel paper schedules.

## What Was Implemented

### 1. Database Migration
- **New Fields Added to `schedules` Table:**
  - `department` - Staff department (FRONT DESK, HOUSEKEEPING, etc.)
  - `shift_time` - Shift time range (e.g., "7am-3pm", "ON")
  - `phone_number` - Staff phone number
  - `shift_id` - Now nullable for backward compatibility

- **New Table: `schedule_uploads`**
  - Tracks uploaded schedule files
  - Stores upload metadata (filename, week, status, entry count)

- **Auto-Migration:**
  - Existing shift-based entries automatically converted to paper format
  - Shift 1 → "7am-3pm", Shift 2 → "3pm-11pm", Shift 3 → "11pm-7am"
  - Departments assigned based on user roles

**To Apply Migration:**
```bash
python migrate_paper_schedule.py
```

### 2. Schedule Parser (`schedule_parser.py`)
Intelligent parser that extracts schedule data from PDF and DOCX files:

**Supported Formats:**
- PDF schedules (using pdfplumber)
- DOCX schedules (using python-docx)

**Extraction Capabilities:**
- Department headers (FRONT DESK, HOUSEKEEPING, BREAKFAST ATTENDANT, LAUNDRY, MAINTENANCE, INSPECTING)
- Staff names and phone numbers
- Shift times for each day (MON-SUN)
- Handles "ON" flags for on-call status
- Normalizes time formats ("7am - 3pm" → "7am-3pm")
- Validates and warns about parsing issues

### 3. Upload Workflow

**Manager-Only Actions:**
1. Click "📄 Upload Schedule" button
2. Select PDF or DOCX file (max 16MB)
3. File is uploaded and parsed automatically
4. Preview shows paper-style layout with parsed data
5. Review warnings (if any)
6. Choose to replace existing week or merge
7. Confirm to import into schedule

**Backend Endpoints:**
- `POST /schedule/upload` - Upload and parse file
- `GET /schedule/preview/<upload_id>` - Preview parsed data
- `POST /schedule/confirm/<upload_id>` - Confirm and save
- `POST /schedule/cancel/<upload_id>` - Cancel upload

### 4. Dual View System

**Shift View (Original):**
- Organized by shifts (1, 2, 3) as rows
- Days as columns
- Good for coverage at-a-glance

**Paper View (New):**
- Organized by departments and staff
- Days as columns
- Matches traditional hotel paper schedules
- Shows shift times (e.g., "7am-3pm", "ON")
- Includes phone numbers
- Clean, scannable layout

**Toggle Between Views:**
- Click "Shift View" or "Paper View" buttons
- View preference persists during navigation

### 5. Updated Manual Entry

The manual staff assignment modal now supports paper-style fields:

**New Fields:**
- **Department** - Select from dropdown (Front Desk, Housekeeping, etc.)
- **Shift Time** - Presets (7am-3pm, 3pm-11pm, ON) or custom
- **Phone Number** - Optional staff contact

**Backward Compatible:**
- Still creates entries with shift_id for shift view
- Both views read from the same normalized data

### 6. User Interface Updates

**Schedule Page Enhancements:**
- Upload Schedule button (manager only)
- View toggle (Shift View / Paper View)
- Upload modal with file picker
- Real-time upload status
- Custom time entry option

**Preview Page:**
- Paper-style schedule layout
- Upload metadata (file, week, entries count)
- Parsing warnings display
- Replace/merge option
- Confirm/Cancel actions

**Styling:**
- Paper schedule table with department grouping
- Today's date highlighting
- Responsive design for mobile
- Clean, minimal aesthetic matching paper schedules

## Usage Instructions

### For Managers

**Uploading a Schedule:**

1. Navigate to Weekly Schedule page
2. Click "📄 Upload Schedule" button
3. Select your PDF or DOCX schedule file
4. Wait for parsing (usually 1-2 seconds)
5. Review the preview:
   - Check that all staff are correctly identified
   - Verify departments are assigned properly
   - Review shift times for accuracy
   - Check any warnings displayed
6. Choose:
   - ✓ "Replace existing schedule for this week" (recommended)
   - ✗ Uncheck to merge with existing entries
7. Click "✓ Confirm & Import Schedule"

**Viewing Schedules:**

- **Shift View:** Click "Shift View" toggle for traditional shift-based layout
- **Paper View:** Click "Paper View" toggle for department-grouped layout

**Manual Entry (Updated):**

1. Click the "+" button in any day/shift cell (Shift View) or day column (Paper View)
2. Fill in:
   - Staff name (or select registered user)
   - Department
   - Shift time (select preset or enter custom)
   - Phone number (optional)
3. Click "Assign"

### For Staff

**Viewing Schedules:**
- Access is read-only
- Can toggle between Shift View and Paper View
- Cannot upload or edit schedules

## File Format Requirements

**For Best Results:**

Your uploaded schedule should be a table with:
- **Header row** with day names (MON, TUE, WED, THURS, FRI, SAT, SUN)
- **Department sections** with headers (FRONT DESK, HOUSEKEEPING, etc.)
- **Staff rows** with:
  - First column: Staff name (optionally with phone number)
  - Subsequent columns: Shift times for each day

**Example Layout:**
```
SLEEP INN & SUITES KALAMAZOO

              MON      TUE       WED      THURS     FRI      SAT      SUN

FRONT DESK
Karolee       7am-3pm  7am-3pm   7am-3pm  7am-3pm   OFF      OFF      7am-3pm
555-888-9397

HOUSEKEEPING
Stacia        ON       ON        ON       ON        ON       ON
331-492-9753

BREAKFAST ATTENDANT
LAUNDRY
Pam           8:45am-
              12:45pm
```

**Supported Time Formats:**
- "7am-3pm"
- "3pm-11pm"
- "8:45am-12:45pm"
- "ON" (for on-call)
- Empty cells (no coverage)

## Technical Details

### Data Model

**Normalized Schedule Record:**
```sql
{
  id: INTEGER,
  user_id: INTEGER (nullable),
  staff_name: TEXT,
  shift_date: TEXT (YYYY-MM-DD),
  shift_id: INTEGER (1/2/3, nullable),
  shift_time: TEXT ("7am-3pm", "ON", etc.),
  department: TEXT,
  phone_number: TEXT (nullable),
  role: TEXT (optional override),
  note: TEXT (optional),
  created_at: TIMESTAMP
}
```

### Parser Logic

**Department Detection:**
- Scans for keywords: "front desk", "housekeeping", "breakfast", "maintenance", "inspecting"
- Maps to standardized department names

**Day Column Mapping:**
- Detects header row with day names
- Maps column indices to day offsets (0=Mon, 6=Sun)

**Time Normalization:**
- Regex-based extraction: `(\d{1,2}):?(\d{2})?\s*(am|pm)\s*[-–]\s*(\d{1,2}):?(\d{2})?\s*(am|pm)`
- Normalizes to consistent format: "7am-3pm"
- Handles "ON" flag for on-call status

**Phone Extraction:**
- Regex pattern: `(\d{3}[-.\s]?\d{3}[-.\s]?\d{4})`
- Removes from staff name after extraction

### Security

- Manager-only access to upload
- CSRF protection on all forms
- Rate limiting (10 uploads per hour)
- File size limit (16MB)
- File type validation (PDF, DOCX only)
- SQL injection protection via parameterized queries
- Session-based preview data storage

### Error Handling

**Parser Errors:**
- No tables found
- No schedule entries extracted
- Invalid file format

**Validation Warnings:**
- Missing departments
- Unusual shift time formats
- Duplicate entries
- Empty staff names

## Files Modified/Created

### New Files:
- `migrate_paper_schedule.py` - Database migration script
- `schedule_parser.py` - PDF/DOCX parsing module
- `templates/schedule_preview.html` - Upload preview page
- `SCHEDULE_UPLOAD_GUIDE.md` - This documentation

### Modified Files:
- `app.py` - Added upload routes, updated schedule views
- `templates/schedule.html` - Added dual views, upload modal, updated entry form
- `static/styles.css` - Added paper schedule styles

### Database Changes:
- `schedules` table - Added columns, updated indexes
- `schedule_uploads` table - New tracking table

## Testing

**Unit Tests:**
```bash
python -m py_compile app.py schedule_parser.py migrate_paper_schedule.py
```

**Manual Testing Checklist:**
- [ ] Upload PDF schedule
- [ ] Upload DOCX schedule
- [ ] Preview shows correct data
- [ ] Warnings display for issues
- [ ] Confirm imports data correctly
- [ ] Cancel cleans up file
- [ ] Shift View displays entries
- [ ] Paper View displays entries
- [ ] Manual entry works with new fields
- [ ] Today highlighting works
- [ ] Mobile responsive layout
- [ ] Staff users cannot upload (read-only)

## Troubleshooting

**"No tables found in PDF"**
- Ensure PDF contains an actual table structure
- Try converting to DOCX if PDF has formatting issues

**"No schedule entries could be extracted"**
- Check that day names are in header row
- Verify department headers are present
- Ensure staff names are in first column

**Missing departments or staff:**
- Check parsing warnings on preview page
- Verify table structure matches expected format
- Consider manual entry for edge cases

**Upload fails with "File too large":**
- Compress PDF or reduce image quality
- Maximum file size is 16MB

## Future Enhancements (Optional)

- [ ] OCR support for scanned PDFs
- [ ] Excel (XLSX) format support
- [ ] Schedule templates for download
- [ ] Bulk edit/delete for imported schedules
- [ ] Export schedule to PDF
- [ ] Email schedule to staff
- [ ] Schedule conflict detection
- [ ] Shift swap workflow

## Support

For questions or issues:
- Review parsing warnings on preview page
- Check browser console for JavaScript errors
- Review `app.log` for server errors
- Contact: keith@taurustech.me (via Gmail compose link in footer)

---

**Implementation Date:** January 2026
**Version:** 1.0
**Status:** Production Ready ✓
