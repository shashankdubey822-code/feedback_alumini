# CLAUDE HAIKU — STRICT TASK PROTOCOL
<!--
  READ THIS FULLY BEFORE TOUCHING ANY FILE.
  VIOLATING ANY RULE BELOW = YOUR EDIT IS WRONG.
-->

---

## 🔒 HARD RULES — NO EXCEPTIONS

```
RULE 1: You edit EXACTLY ONE file per task. Not two. Not zero. ONE.
RULE 2: You edit ONLY the lines specified. No reformatting. No style fixes.
RULE 3: You do NOT run any command (no npm, no python, no pip, nothing).
RULE 4: You do NOT move to the next task until you see "UNLOCKED" in ANTIGRAVITY.md.
RULE 5: After your edit, you MUST append your log to ANTIGRAVITY.md. Nothing else.
RULE 6: If the line number doesn't match what you see, STOP. Write "BLOCKED" in ANTIGRAVITY.md and wait.
RULE 7: Do not explain. Do not summarize. Do not suggest. Just edit and log.
```

---

## 🔴 CURRENT TASK — TASK 1 (UNLOCKED)

**Status:** UNLOCKED ✅
**File:** `backend/services/job_worker.py`
**Action:** INSERT one line
**Where:** Find the last `import` line at the top of the file
**Insert AFTER that line:**
```python
from backend.utils.insforge_db import api_update
```
**Do NOT change any other line.**
**Do NOT add blank lines.**
**Do NOT reformat imports.**

### After your edit, append EXACTLY this to `ANTIGRAVITY.md` under `## Haiku Log`:
```
### TASK 1 — DONE
- File: backend/services/job_worker.py
- Action: Added import line after last import
- Line inserted: from backend.utils.insforge_db import api_update
- Waiting for Antigravity review.
```

### Then STOP. Do not read Task 2. Do not plan Task 2. STOP.

---
**Your job:** Create ONE new file.
**File to create:** `migrations/task3_feedback_responses_columns.sql`
**Write EXACTLY this content — nothing more:**
```sql
ALTER TABLE feedback_responses
  ADD COLUMN IF NOT EXISTS extracted_date DATE,
  ADD COLUMN IF NOT EXISTS extracted_time TIME,
  ADD COLUMN IF NOT EXISTS session_technical_clarity INTEGER,
  ADD COLUMN IF NOT EXISTS form_source VARCHAR(50) DEFAULT 'google_form',
  ADD COLUMN IF NOT EXISTS record_status VARCHAR(20) DEFAULT 'active';
```
**Do NOT edit any Python file. Do NOT run any command. Create the file. Stop.**

After creating the file, append to `ANTIGRAVITY.md` under `## Haiku Log`:
```
### TASK 3 — DONE
- File created: migrations/task3_feedback_responses_columns.sql
- Columns: extracted_date, extracted_time, session_technical_clarity, form_source, record_status
- Table: feedback_responses
- Waiting for Antigravity review.
```
Then STOP.

---

## ✅ TASK 2 — COMPLETE
**File created:** `migrations/task2_events_columns.sql` ✅
**User action required:** Run that SQL file in InsForge SQL editor.

---

## 🔒 TASK 3 — LOCKED

**Status:** LOCKED 🔒

<details>
<summary>Click only after ANTIGRAVITY.md shows TASK 3 UNLOCKED</summary>

**File to create:** `migrations/task3_feedback_responses_columns.sql`
**Action:** Create that file with this exact content:

```sql
ALTER TABLE feedback_responses
  ADD COLUMN IF NOT EXISTS extracted_date DATE,
  ADD COLUMN IF NOT EXISTS extracted_time TIME,
  ADD COLUMN IF NOT EXISTS session_technical_clarity INTEGER,
  ADD COLUMN IF NOT EXISTS form_source VARCHAR(50) DEFAULT 'google_form',
  ADD COLUMN IF NOT EXISTS record_status VARCHAR(20) DEFAULT 'active';
```

Log to ANTIGRAVITY.md:
```
### TASK 3 — DONE
- File created: migrations/task3_feedback_responses_columns.sql
- Action: Wrote SQL to add 5 missing columns to feedback_responses
- User must run this SQL in InsForge dashboard.
- Waiting for Antigravity review.
```
Then STOP.

</details>

---

## 🔒 TASK 4 — LOCKED

**Status:** LOCKED 🔒

<details>
<summary>Click only after ANTIGRAVITY.md shows TASK 4 UNLOCKED</summary>

**File to create:** `migrations/task4_speakers_table.sql`
```sql
CREATE TABLE IF NOT EXISTS speakers (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name VARCHAR(255) UNIQUE NOT NULL,
  department VARCHAR(255),
  bio TEXT,
  linkedin_url VARCHAR(500),
  created_at TIMESTAMPTZ DEFAULT now()
);
ALTER TABLE events ADD COLUMN IF NOT EXISTS speaker_id UUID REFERENCES speakers(id);
```

Log to ANTIGRAVITY.md:
```
### TASK 4 — DONE
- File created: migrations/task4_speakers_table.sql
- Action: Wrote SQL to create speakers table and add speaker_id FK to events
- User must run this SQL in InsForge dashboard.
- Waiting for Antigravity review.
```
Then STOP.

</details>

---

## 🔒 TASK 5 — LOCKED

**Status:** LOCKED 🔒

<details>
<summary>Click only after ANTIGRAVITY.md shows TASK 5 UNLOCKED</summary>

**File:** `backend/routes/admin.py`
**Action:** Find the dict where events are inserted (search for `api_insert('events'` or `api_insert("events"`).
Find the dict payload passed to it.
Add these 3 keys to that dict ONLY:
```python
'form_url': form_url,
'form_id': form_id,
'form_edit_url': form_edit_url,
```
**Do NOT change anything else in the file.**

Log to ANTIGRAVITY.md:
```
### TASK 5 — DONE
- File: backend/routes/admin.py
- Action: Added form_url, form_id, form_edit_url to events insert payload
- Lines modified: [write actual line numbers here]
- Waiting for Antigravity review.
```
Then STOP.

</details>

---

## 🔒 TASK 6 — LOCKED

**Status:** LOCKED 🔒

<details>
<summary>Click only after ANTIGRAVITY.md shows TASK 6 UNLOCKED</summary>

**File:** `migrations/task6_backfill_speakers.sql`
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

Log to ANTIGRAVITY.md:
```
### TASK 6 — DONE
- File created: migrations/task6_backfill_speakers.sql
- Action: Backfill SQL to populate speakers table from existing events data
- User must run this in InsForge dashboard AFTER tasks 4 is run.
- Waiting for Antigravity review.
```
Then STOP.

</details>

---

## ⛔ WHAT HAPPENS IF YOU BREAK A RULE

If you edit more than specified → the user will revert your change.
If you skip the ANTIGRAVITY.md log → your task is considered NOT DONE.
If you proceed to a locked task → Antigravity will reject all your work.
