# InsForge Backend Infrastructure

This directory contains InsForge-native backend components that replace
the Hugging Face polling workers.

## Directory Structure

```
insforge/
├── triggers/
│   ├── feedback_trigger.sql      # DB trigger: fires on INSERT into feedback_responses
│   └── certificate_trigger.sql  # DB trigger: fires on INSERT into certificate_jobs
└── functions/
    ├── process-feedback/
    │   └── index.ts             # Edge Function: NLP analysis + embedding
    └── send-certificate/
        └── index.ts             # Edge Function: Certificate email via Apps Script
```

## Deployment Steps

### 1. Deploy DB Triggers (run once in InsForge SQL Editor)

```sql
-- Run feedback_trigger.sql first
-- Run certificate_trigger.sql second
```

### 2. Deploy Edge Functions (InsForge Dashboard → Edge Functions)

**Function: process-feedback**
- Slug: `process-feedback`
- Source: copy contents of `functions/process-feedback/index.ts`
- Environment Variables required:
  - `OPENROUTER_API_KEY` — your InsForge-provisioned OpenRouter key
  - `INSFORGE_BASE_URL` — `https://ajas4w5j.us-east.insforge.app`
  - `ANON_KEY` — your InsForge anon key

**Function: send-certificate**
- Slug: `send-certificate`
- Source: copy contents of `functions/send-certificate/index.ts`
- Environment Variables required:
  - `INSFORGE_BASE_URL`
  - `ANON_KEY`
  - `APPS_SCRIPT_URL` — your Google Apps Script webhook URL
  - `APPS_SCRIPT_SECRET` — your shared secret (optional but recommended)

### 3. Environment Variables Required on Hugging Face Space

Add this to your HF Space secrets:
```
OPENROUTER_API_KEY=<get from InsForge Dashboard → AI → OpenRouter Key>
```

## Architecture After Deployment

```
Google Form submitted
    ↓
InsForge DB: INSERT into feedback_responses
    ↓ (feedback_trigger.sql fires)
InsForge Realtime publishes 'feedback:new'
    ↓ (HF Flask app is subscribed via InsForge SDK)
HF Flask calls POST /api/functions/process-feedback
    ↓
Edge Function: NLP via Gemini 2.5 Flash (free) + Embedding via text-embedding-3-small
    ↓
Saves to feedback_analysis + updates embedding column
```

**Result: dl_worker.py polling loop is completely eliminated.**
