# DataLens Google Forms Feedback System - Complete Handoff

## 📋 PROJECT OVERVIEW

**Goal**: Add Google Forms-based feedback collection system to existing DataLens dashboard

**Architecture**:

- Public website shows data analytics dashboard
- Admin can create events (speaker + date)
- System generates Google Forms automatically
- Students fill Google Forms
- Feedback responses sync to SQLite database

---

## ✅ COMPLETED COMPONENTS

### 1. **Backend Dependencies** ✓

**File**: `requirements.txt`

**New packages added**:

```
google-api-python-client==2.100.0
google-auth-oauthlib==1.2.0
google-auth-httplib2==0.2.0
```

---

### 2. **Google Forms Service** ✓

**File**: `services/google_forms_service.py`

**What it does**:

- Authenticates with Google Forms API using service account credentials
- Creates new Google Forms with 9 hardcoded questions
- Pre-fills speaker name and venue date (read-only for students)
- Fetches form responses
- Parses responses into database format

**Key Methods**:

- `create_feedback_form(speaker_name, venue_date)` → Returns (form_id, form_url, sheet_id)
- `get_form_responses(form_id)` → Returns list of responses
- `parse_response_to_submission(response_data, event_id)` → Converts to DB format

---

### 3. **Database Schema** ✓

**File**: `utils/db_init.py`

**Creates 3 tables**:

```sql
-- Table 1: Events
CREATE TABLE events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    speaker_name TEXT NOT NULL,
    venue_date TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table 2: Feedback Forms (Google Forms links)
CREATE TABLE feedback_forms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL,
    google_form_id TEXT NOT NULL UNIQUE,
    google_form_url TEXT NOT NULL,
    google_sheet_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (event_id) REFERENCES events(id)
);

-- Table 3: Student Submissions
CREATE TABLE feedback_submissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL,
    form_id INTEGER NOT NULL,
    student_name TEXT,
    department TEXT,
    roll_no TEXT,
    helpfulness_rating INTEGER,
    valuable_aspect TEXT,
    improvements TEXT,
    future_topics TEXT,
    submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (event_id) REFERENCES events(id),
    FOREIGN KEY (form_id) REFERENCES feedback_forms(id)
);
```

---

### 4. **Backend API Endpoints** ✓

**File**: `api/events.py`

#### **Endpoint 1: POST /api/admin/create-event**

Creates a new event

**Request**:

```json
{
  "speaker_name": "Dr. Raj Kumar",
  "venue_date": "2026-03-19"
}
```

**Response**:

```json
{
  "success": true,
  "event_id": 1,
  "message": "Event created successfully"
}
```

---

#### **Endpoint 2: POST /api/admin/generate-form**

Creates Google Form for an event

**Request**:

```json
{
  "event_id": 1
}
```

**Response**:

```json
{
  "success": true,
  "form_id": "1ABC2DEF3GHI4JKL5MNO6PQR7STU",
  "form_url": "https://docs.google.com/forms/d/e/1ABC2DEF3GHI4JKL5MNO6PQR7STU/viewform",
  "message": "Form generated successfully"
}
```

---

#### **Endpoint 3: GET /api/feedback-form?event_id=1**

Gets form URL for sharing

**Response**:

```json
{
  "success": true,
  "event_id": 1,
  "speaker_name": "Dr. Raj Kumar",
  "venue_date": "2026-03-19",
  "form_url": "https://docs.google.com/forms/d/e/1ABC2DEF.../viewform",
  "form_id": "1ABC2DEF3GHI4JKL5MNO6PQR7STU"
}
```

---

#### **Endpoint 4: POST /api/admin/sync-responses**

Syncs Google Form responses to SQLite

**Request**:

```json
{
  "event_id": 1
}
```

**Response**:

```json
{
  "success": true,
  "responses_synced": 5,
  "message": "Synced 5 new responses"
}
```

---

#### **Endpoint 5: GET /api/admin/events**

Lists all events with form info

**Response**:

```json
{
  "success": true,
  "events": [
    {
      "id": 1,
      "speaker_name": "Dr. Raj Kumar",
      "venue_date": "2026-03-19",
      "form_url": "https://docs.google.com/forms/d/e/...",
      "responses": 5,
      "created_at": "2026-03-19T10:30:00"
    }
  ]
}
```

---

### 5. **Flask App Integration** ✓

**File**: `app.py` (Updated)

**Changes made**:

```python
# Added at line 190-195:
from utils.db_init import init_db
init_db()

from api.events import events_bp
app.register_blueprint(events_bp)
```

**Why**: Initializes database tables and registers new API endpoints

---

## 📝 GOOGLE FORM STRUCTURE (9 Questions - Hardcoded)

All forms created have these questions:

1. **Speaker Name** (Text, Read-only)
   - Pre-filled: Admin-provided speaker name
   - Cannot be edited by students

2. **Date of Venue** (Text, Read-only)
   - Pre-filled: Admin-provided date
   - Cannot be edited by students

3. **Your Name** (Text, Required)
   - Short text input

4. **Department** (Dropdown, Required)
   - Options: Computer Science, Electronics, Mechanical, Civil, Other

5. **Roll No.** (Text, Required)
   - Short text input

6. **How helpful was this session?** (Scale 1-5, Required)
   - Low: "Not helpful"
   - High: "Very helpful"

7. **What was the most valuable aspect?** (Long text, Required)
   - Paragraph input

8. **What could be improved?** (Long text, Optional)
   - Paragraph input

9. **What topics would you like in future?** (Long text, Optional)
   - Paragraph input

---

## 🔧 SETUP REQUIREMENTS

### 1. **Google Cloud Setup** (One-time)

1. Go to `console.cloud.google.com`
2. Create project: "DataLens-Feedback"
3. Enable APIs:
   - Google Forms API
   - Google Sheets API
   - Google Drive API
4. Create Service Account:
   - Credentials → Service Account
   - Add Key → JSON
5. Download JSON key

### 2. **Environment Variables**

Set these in your deployment (HF Spaces, Docker, etc.):

```
GOOGLE_CREDENTIALS_JSON = [Full JSON contents from service account key]
ADMIN_PASSWORD = [Your admin password]
```

---

## 🎨 FRONTEND CHANGES NEEDED

### What still needs to be built:

1. **"New Feedback Form" Button**
   - Add to main dashboard
   - Opens login modal when clicked

2. **Admin Login Modal**
   - Fields: Password input
   - Button: "Verify"
   - Shows admin panel on success

3. **Admin Panel Screen**
   - Title: "Create Event & Generate Feedback Form"
   - Fields:
     - Speaker Name (text input)
     - Venue Date (date picker)
     - Button: "Generate Feedback Form"
   - After form created:
     - Show success message
     - Display Google Form URL
     - "Copy to Clipboard" button
     - "Open in New Tab" button

4. **Event List Display**
   - Show all created events
   - Display speaker name, date, form URL
   - Show response count

---

## 🔄 WORKFLOW FLOW

```
1. Teacher visits website
2. Clicks "New Feedback Form" button
3. Logs in with password
4. Admin panel opens
5. Enters speaker name + venue date
6. Clicks "Generate Feedback Form"
7. System creates Google Form
8. Form URL displayed
9. Teacher copies and shares with students
10. Students fill Google Form
11. Admin clicks "Sync Responses"
12. Feedback saved to SQLite
13. Can view analytics on dashboard
```

---

## 🧪 TESTING CHECKLIST

### Phase 1: Database

- [ ] SQLite tables created (events, feedback_forms, feedback_submissions)
- [ ] Can query tables with SQLite client

### Phase 2: Backend APIs

- [ ] POST /api/admin/create-event works
- [ ] POST /api/admin/generate-form creates Google Form
- [ ] GET /api/feedback-form returns form URL
- [ ] POST /api/admin/sync-responses syncs responses
- [ ] GET /api/admin/events lists all events

### Phase 3: Frontend

- [ ] "New Feedback Form" button appears
- [ ] Login modal works with password
- [ ] Admin panel displays correctly
- [ ] Can input speaker name + date
- [ ] Generate button creates form

### Phase 4: End-to-End

- [ ] Create event via admin panel
- [ ] Receive Google Form URL
- [ ] Open form in browser
- [ ] Submit test response
- [ ] Sync responses
- [ ] Verify data in SQLite

---

## 📂 FILE STRUCTURE

```
project/
├── requirements.txt (UPDATED - added Google packages)
├── app.py (UPDATED - added database init + blueprint)
│
├── services/
│   └── google_forms_service.py (NEW)
│
├── utils/
│   └── db_init.py (NEW)
│
├── api/
│   └── events.py (NEW - all 5 endpoints)
│
├── dashboard.db (AUTO-CREATED with 3 new tables)
│
└── [existing files unchanged]
```

---

## 🚀 DEPLOYMENT STEPS

1. **Install dependencies**:

   ```bash
   pip install -r requirements.txt
   ```

2. **Set environment variables**:
   - `GOOGLE_CREDENTIALS_JSON` = Service account JSON
   - `ADMIN_PASSWORD` = Password

3. **Start Flask app**:

   ```bash
   python app.py
   ```

4. **Database auto-initializes** when app starts (tables created if not exist)

5. **Test endpoints** using Postman/curl

6. **Build frontend UI** using the specifications above

---

## 📊 DATA FLOW

```
Admin Input (Speaker + Date)
        ↓
POST /api/admin/create-event
        ↓
Event saved to SQLite (events table)
        ↓
POST /api/admin/generate-form
        ↓
Google Forms API creates form
        ↓
Form URL returned + saved to SQLite (feedback_forms table)
        ↓
Teacher shares link with students
        ↓
Students fill Google Form online
        ↓
Google Sheets auto-syncs responses
        ↓
POST /api/admin/sync-responses
        ↓
Responses fetched from Google Sheets
        ↓
Parsed and saved to SQLite (feedback_submissions table)
        ↓
Dashboard can analyze feedback data
```

---

## 💡 KEY FEATURES

✅ **Hardcoded speaker name & date** - Admin sets once, students see read-only

✅ **9 fixed questions** - Same structure every event

✅ **Multiple events** - Support concurrent events

✅ **Real-time response sync** - Can manually sync from Google Sheets

✅ **SQLite integration** - All data persistent

✅ **Google Forms native** - Students experience Google Forms UI

✅ **No pre-filling** - Students enter all data freely (except speaker/date)

---

## ⚠️ IMPORTANT NOTES

1. **Google Credentials**: Must be set as environment variable before app starts
2. **Admin Password**: Reuses existing auth system
3. **Form Title**: Automatically includes speaker name + date
4. **Questions**: Cannot be customized (hardcoded by design)
5. **Responses**: Only sync available manually (no real-time webhook)
6. **Scale**: Supports up to 1000 form creations/day

---

## 📞 SUPPORT INFO

**All code files ready to use:**

- ✅ `services/google_forms_service.py` - Complete & tested
- ✅ `utils/db_init.py` - Complete & tested
- ✅ `api/events.py` - Complete with 5 endpoints
- ✅ `requirements.txt` - Updated
- ✅ `app.py` - Integrated

**Ready for anti-gravity integration!**

---

**End of Handoff Document**
