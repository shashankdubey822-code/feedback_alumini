# Ultimate AI Context: Alumni Feedback System (`mamta_01`)

This document serves as the absolute "source of truth" and architectural blueprint for the Alumni Feedback System project. Any AI agent reading this file instantly gains complete contextual knowledge of the codebase, tech stack, workflows, and rules of engagement.

## 1. Project Overview & Architecture
The Alumni Feedback System is a full-stack web application designed to collect, process, and analyze feedback from students regarding guest lectures given by alumni. 
It features automated data ingestion (via Google Forms webhooks), deep learning-based NLP analysis (sentiment & keyword extraction), RAG-based document chatting (Wiki), and automated certificate generation (via Google Apps Script).

**Core Deployment Target:** Hugging Face Spaces.

## 2. Tech Stack & Environment
### Backend
*   **Framework:** Flask (`app.py` is the entry point).
*   **Database:** SQLite (`dashboard.db`).
*   **Data Processing:** Pandas, NumPy.
*   **NLP & ML:** TextBlob, NLTK, KeyBERT, BERTopic, SentenceTransformers.
*   **AI Orchestration:** LangChain (LangChain Core, Groq, Google GenAI, Cohere, Mistral).
*   **Cloud Storage/Vector DB:** Supabase (Used for Wiki documents and vector search).

### Frontend
*   **Tech:** Vanilla HTML, CSS, JavaScript (served statically from the `frontend/` directory).
*   **Key Files:** `index.html`, `app.js`, `style.css`.

### Integrations
*   **Google Apps Script:** Used asynchronously to generate certificates and send emails based on Google Slides templates.

## 3. Directory Structure
```
/
├── app.py                     # Main Flask Application Factory
├── AI_INSTRUCTIONS.md         # Fast-rules for AI agents
├── AI_CONTEXT.md              # THIS FILE (Master Context)
├── requirements.txt           # Python dependencies
├── backend/
│   ├── config.py              # Environment & App Configuration
│   ├── models/                # Dataclasses & Schemas (schemas.py)
│   ├── routes/                # Flask Blueprints (api.py, admin.py, webhook.py, health.py, wiki.py)
│   ├── services/              # Business Logic & Workers
│   │   ├── dl_worker.py       # Background Thread: NLP & Deep Learning processing
│   │   ├── job_worker.py      # Background Thread: Certificate Generation (Calls GAS)
│   │   ├── nlp_service.py     # Sentiment and Keyword extraction logic
│   │   ├── wiki_service.py    # RAG/Supabase logic for document retrieval
│   ├── utils/                 # Helpers (logger.py, db_helper.py)
├── frontend/                  # Static assets (HTML, JS, CSS)
├── google_apps_script/        # Source code for Google Apps Script deployed externally
```

## 4. Database Schema (SQLite: `dashboard.db`)
The application uses SQLite as its primary relational store.
Key Tables:
*   **`dashboard_data`**: The central table storing all student feedback.
    *   *Core Columns:* `id`, `name_of_student`, `roll_no_cleaned`, `department_cleaned`, `date_of_lecture`, `alumni_speaker_name`.
    *   *Feedback Columns:* `session_rating`, `session_technical_clarity`, `improvements_suggestions`, `future_topics`, `aspect_most_valuable`.
    *   *AI Metadata Columns:* `dl_processed`, `dl_sentiment_score`, `dl_sentiment_label`, `dl_keywords` (Stores JSON).
*   **`job_queue`**: Tracks background jobs for certificate generation.
    *   *Columns:* `id`, `event_id`, `student_name`, `student_email`, `status` (pending, processing, completed, failed), `attempts`.
*   **`events`**: Maps form submissions to specific lecture events and links the Google Slides `template_id`.

## 5. Critical Workflows
### A. Data Ingestion (Webhook Flow)
1.  A Google Form submission hits `/webhook/google-forms`.
2.  `webhook.py` parses the payload, normalizes timestamps and Roll Numbers using regex (`^2[Kk]\d{2}[A-Za-z]{3,12}\d{5}$`), and inserts the raw data into `dashboard_data`.

### B. Background Deep Learning Analysis (`dl_worker.py`)
1.  A background daemon thread continuously polls `dashboard_data` for rows where `dl_processed = 0`.
2.  It runs `NLPService` to perform sentiment analysis, keyword extraction, and "actionable" categorization.
3.  Results are stored back into the row as a JSON payload in the `dl_keywords` column.

### C. Certificate Generation (`job_worker.py`)
1.  When an event is marked to send certificates, entries are added to `job_queue` in `admin.py`.
2.  `job_worker.py` (daemon thread) polls for `pending` jobs.
3.  It makes a POST request to an external Google Apps Script URL with student details and the `template_id`.
4.  GAS handles the heavy lifting (replacing text in Google Slides, exporting to PDF, sending via Gmail) and returns success/failure.

### D. RAG / Wiki Pipeline (`wiki_service.py`)
1.  Administrators upload documents (PDF/Audio/Wiki text).
2.  Text is chunked and embedded using local SentenceTransformers (`all-MiniLM-L6-v2`) or via API.
3.  Embeddings are stored in **Supabase (pgvector)**.
4.  LangChain orchestrates retrieval, using **Groq** (primary, for speed) with an automated fallback to **Gemini** if Groq rate-limits (429) or times out.

## 6. Strict Rules of Engagement for AI Agents
1.  **Deployment Reality:** The app runs on **Hugging Face Spaces**. The file system is ephemeral. Do not create local files expecting them to persist across restarts unless they are in configured persistent storage (if any). Do NOT run `pip install` in the chat; modify `requirements.txt` instead.
2.  **Model Orchestration:** Always respect the Groq -> Gemini fallback chain. If modifying `wiki_service.py` or AI orchestration, ensure error handling gracefully catches timeouts and switches models automatically.
3.  **No Hardcoding AI Logic:** When updating prompt templates or AI logic, ensure the AI acts dynamically on the provided context (e.g., Supabase vectors or SQLite rows). Do not hardcode specific insights.
4.  **SQL Execution:** SQLite is used heavily in multi-threaded mode. Ensure any new database connections in background workers use `timeout=10.0` or higher to prevent `database is locked` errors.
