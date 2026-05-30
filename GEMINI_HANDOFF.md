# GEMINI HANDOFF — Alumni Feedback System
> You are Gemini 2.5 Pro in VS Code (GitHub Copilot).
> The user's Antigravity AI limit is exhausted. You are now the PRIMARY AI.
> Read this entire file before doing ANYTHING.

---

## 🎯 PROJECT GOAL
An **Alumni Feedback System** deployed on **Hugging Face Spaces** (backend) with an **InsForge PostgreSQL** database. Students submit feedback via Google Forms after guest speaker sessions. The admin dashboard analyzes feedback using AI (LangChain agents + NLP).

**Stack:**
- Backend: Flask + Python on Hugging Face Spaces
- Database: InsForge (PostgreSQL via PostgREST REST API)
- AI: LangChain 5-agent pipeline (Groq/Gemini/OpenRouter fallback)
- Frontend: Vanilla JS + Chart.js (served by Flask)
- Google Apps Script (GAS): generates Google Forms, sends webhook to Flask

**Project path:** `c:\Users\hp\OneDrive - Manav Rachna Education Institutions\Desktop\OWN_2025\mamta_01\`

---

## 📊 WHAT WAS COMPLETED (verified on InsForge)

| Task | What was done | Verified |
|---|---|---|
| Task 1 | Added `from backend.utils.insforge_db import api_update` to `backend/services/job_worker.py` line 17 | ✅ |
| Task 2 | Added `form_url`, `form_id`, `form_edit_url` columns to `events` table in InsForge | ✅ |
| Task 3 | Added `extracted_date`, `extracted_time`, `session_technical_clarity`, `form_source`, `record_status` to `feedback_responses` table | ✅ |
| Task 4 | Created `speakers` table in InsForge + added `speaker_id UUID FK` to `events` table | ✅ |

---

## ❌ WHAT IS STILL BROKEN (your job)

### Task 5 — Fix `admin.py` event creation payload
**File:** `backend/routes/admin.py`
**Problem:** When a new event is created, the code tries to save `form_url`, `form_id`, `form_edit_url` to the database but these keys are missing from the insert payload dict.
**What to do:**
1. Open `backend/routes/admin.py`
2. Search for where events are inserted into the DB (search for `'speaker_name'` — that's inside the events payload dict)
3. Find the dict that gets inserted — it has keys like `speaker_name`, `venue_date`, `department`
4. Add these 3 keys to that same dict:
```python
'form_url': form_url,
'form_id': form_id,
'form_edit_url': form_edit_url,
```
5. Make sure `form_url`, `form_id`, `form_edit_url` variables are defined above that dict (they come from the GAS response)
6. Save. Log to `ANTIGRAVITY.md` under `## Haiku Log`:
```
### TASK 5 — DONE
- File: backend/routes/admin.py
- Action: Added form_url, form_id, form_edit_url to events insert payload
- Lines modified: [actual line numbers]
- Waiting for review.
```

---

### Task 6 — Backfill speakers table
**File to create:** `migrations/task6_backfill_speakers.sql`
**Content:**
```sql
INSERT INTO speakers (name)
SELECT DISTINCT speaker_name FROM events
WHERE speaker_name IS NOT NULL AND speaker_name <> ''
ON CONFLICT (name) DO NOTHING;

UPDATE events e
SET speaker_id = s.id
FROM speakers s
WHERE e.speaker_name = s.name;
```
After creating file → user pastes SQL into InsForge SQL editor → verify with:
```sql
SELECT COUNT(*) FROM speakers;
```

---

### Task 7 — Fix `webhook.py` event lookup
**File:** `backend/routes/webhook.py`
**Problem:** Webhook tries to find event by `form_id` but was querying a column that didn't exist (now fixed in Task 2). Need to verify the lookup is working.
**What to do:**
1. Open `backend/routes/webhook.py`
2. Search for `form_id`
3. Confirm it queries `events` table using `form_id` column (now exists)
4. If the query uses raw SQL or REST filter like `?form_id=eq.{value}` — it should work now
5. If broken, show the user the exact lines and what to fix

---

## 🗄️ LIVE DATABASE STATE

| Table | Rows | Status |
|---|---|---|
| students | 231 | ✅ |
| events | 41 | ✅ (form_url, form_id, form_edit_url now added) |
| feedback_responses | 287 | ✅ (5 new columns added) |
| feedback_analysis | 287 | ✅ |
| certificate_jobs | 0 | ✅ |
| speakers | 0 | ✅ (created, needs backfill from Task 6) |

---

## 🔧 HOW TO COORDINATE WITH THE USER

**You are in VS Code. The user is the human bridge between you and InsForge.**

### Your rules:
1. **One task at a time.** Never do two things at once.
2. **Verify before moving on.** After every code edit, tell the user what to check.
3. **SQL files only — never run SQL yourself.** Create `.sql` files in `migrations/` folder. User pastes them into InsForge.
4. **After each task**, tell the user:
   - What you changed
   - What file/line
   - What to verify
   - What the next task is

### User's verification method:
- For code edits: User reads the file or searches for the changed line
- For SQL: User pastes into InsForge SQL editor and runs it
- For DB verification: User will ask Gemini or a new AI session to check InsForge

---

## 📋 AFTER ALL TASKS COMPLETE — REMAINING FRONTEND WORK

Once Tasks 5–7 are done, these frontend features need building:

1. **Speaker Profile Page** — Click speaker → see avg rating, keyword cloud, all feedback text
2. **Department Comparison Page** — Side-by-side charts per department
3. **Live WebSocket notification badge** — Already 80% wired in SocketIO
4. **Export CSV button** — Download filtered table
5. **Certificate Job Tracker** — Live status table of cert jobs

---

## ⚠️ CRITICAL RULES — DO NOT BREAK THESE

- **Never run `npm`, `python`, `pip` locally** — cloud-only project
- **Never edit more than specified lines** per task
- **InsForge is the database** — not Supabase, not SQLite
- **The DB utility is** `backend/utils/insforge_db.py` — all DB calls go through it
- **API pattern:** `api_select(table, filter_col, filter_val)` / `api_insert(table, data)` / `api_update(table, pk_col, pk_val, data)` / `api_upsert(table, data, conflict_col)`

---

## 📁 KEY FILES TO KNOW

| File | Purpose |
|---|---|
| `backend/routes/admin.py` | Admin routes: event creation, CSV upload, form generation |
| `backend/routes/webhook.py` | Receives Google Form submissions |
| `backend/routes/api.py` | Dashboard analytics API |
| `backend/agents/data_orchestrator.py` | 5 LangChain agents pipeline |
| `backend/services/dl_worker.py` | Background NLP worker (polls every 5s) |
| `backend/services/job_worker.py` | Certificate generation worker |
| `backend/utils/insforge_db.py` | All DB utility functions |
| `backend/services/analytics_engine.py` | Pandas-based in-memory analytics |
| `CLAUDE.md` | Task queue (ignore — was for Haiku) |
| `ANTIGRAVITY.md` | Progress log — append your task completions here |
| `migrations/` | SQL files created for each task |

---

## ✍️ YOUR FIRST ACTION

Read `backend/routes/admin.py`. Search for `speaker_name` inside a dict. That's the events insert payload. Add `form_url`, `form_id`, `form_edit_url` to it. That is Task 5.
