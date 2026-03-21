# Error Detection & Diagnostics System - README

## Overview

This is a **complete diagnostic system** to identify, monitor, and resolve errors in your DataLens application. It provides deep insights into all systems and subsystems.

## What's New

```
backend/error_detection/          ← NEW ERROR DETECTION SYSTEM
├── __init__.py                   Initialize package
├── error_logger.py               Centralized error tracking (ErrorCategory system)
├── database_checker.py           Database integrity & schema validation
├── nlp_diagnostics.py            NLP service & model health checks
├── data_pipeline_checker.py      Full data ingestion to NLP flow
├── service_status.py             Service availability & configuration

backend/routes/
└── diagnostics.py                ← NEW diagnostic API endpoints

app.py                            ← UPDATED - diagnostics blueprint registered

ANALYSIS_ROOT_CAUSE.md            ← Deep technical analysis of NLP issue
TROUBLESHOOTING_NLP.md            ← Step-by-step fixes for users
ERROR_DETECTION_GUIDE.md          ← Complete system documentation
```

## Quick Start

### 1. Check System Health
```bash
curl http://localhost:7860/api/diagnostics/health
```

This gives you an overview of all systems. Look for `critical_issues` array.

### 2. Diagnose NLP Specifically
```bash
curl http://localhost:7860/api/diagnostics/nlp
```

### 3. Check Data Pipeline
```bash
curl http://localhost:7860/api/diagnostics/pipeline
```

---

## API Endpoints

| Endpoint | Purpose | Response Time |
|----------|---------|---|
| `GET /api/diagnostics/health` | Full system check | 2-3 sec |
| `GET /api/diagnostics/database` | DB schema & data | 1 sec |
| `GET /api/diagnostics/nlp` | NLP service validation | 3-5 sec |
| `GET /api/diagnostics/pipeline` | Data flow status | 1 sec |
| `GET /api/diagnostics/services` | Service availability | 2 sec |
| `GET /api/diagnostics/error-log` | Recent errors | 500ms |

---

## Core Components

### 1. ErrorLogger (`error_logger.py`)
Centralized error tracking system with categorization.

```python
from backend.error_detection import ErrorLogger, ErrorCategory

logger = ErrorLogger()
logger.log_error(
    category=ErrorCategory.NLP_SERVICE,
    error_msg="DistilBERT failed to load",
    context={"model": "distilbert-base-uncased"},
    traceback_str=traceback_text
)
```

**Categories**:
- DATABASE
- NLP_SERVICE
- DATA_INGESTION
- SERVICE_CONNECTION
- BACKGROUND_WORKER
- GOOGLE_FORMS
- CONFIGURATION

### 2. DatabaseChecker (`database_checker.py`)
Validates database schema, data integrity, and processing status.

```python
from backend.error_detection import DatabaseChecker

checker = DatabaseChecker("database/dashboard.db")

# Check everything
full_report = checker.full_check()

# Check specific aspects
schema = checker.check_schema_columns()
data_status = checker.check_data_status()
```

### 3. NLPDiagnostics (`nlp_diagnostics.py`)
Checks NLP service, dependencies, and model availability.

```python
from backend.error_detection import NLPDiagnostics

diag = NLPDiagnostics()

# Full diagnostics
report = diag.full_diagnostics()

# Specific checks
deps = diag.check_nlp_dependencies()
service_ok, msg, detail = diag.check_nlp_service_creation()
```

### 4. DataPipelineChecker (`data_pipeline_checker.py`)
Validates the complete data flow: ingestion → processing → API response.

```python
from backend.error_detection import DataPipelineChecker

checker = DataPipelineChecker("database/dashboard.db")

# Check each stage
ingestion = checker.check_data_ingestion()
queue = checker.check_nlp_processing_queue()
sentiment = checker.check_sentiment_extraction()
keywords = checker.check_keyword_extraction()

# Full report
full_report = checker.full_pipeline_check()
```

### 5. ServiceStatusMonitor (`service_status.py`)
Monitors all service connections and configurations.

```python
from backend.error_detection import ServiceStatusMonitor

monitor = ServiceStatusMonitor()

# Check services
db_ok, msg = monitor.check_database_connection("database/dashboard.db")
gas_ok, msg = monitor.check_google_apps_script_config()
env_vars = monitor.check_environment_variables()
perms = monitor.check_file_permissions("database/dashboard.db")

# Full status
status = monitor.full_status_check("database/dashboard.db")
```

---

## Usage Patterns

### Integration in Flask Route
```python
from flask import Blueprint, jsonify, current_app
from backend.error_detection import DatabaseChecker

my_bp = Blueprint('my_routes', __name__)

@my_bp.route('/my-status')
def check_status():
    db_path = current_app.config.get('DATABASE_PATH')
    checker = DatabaseChecker(db_path)

    status = checker.full_check()

    if status['tables_ok'] and status['data_status']['total_records'] > 0:
        return jsonify({"status": "ok"}), 200
    else:
        return jsonify({"status": "error", "details": status}), 500
```

### In Background Worker
```python
from backend.error_detection import ErrorLogger, ErrorCategory

error_logger = ErrorLogger()

try:
    # Some operation
    nlp = NLPService()
except Exception as e:
    error_logger.log_error(
        category=ErrorCategory.NLP_SERVICE,
        error_msg=f"NLP init failed: {str(e)}",
        traceback_str=traceback.format_exc()
    )
    # Handle error
```

---

## Example Response: Health Check

```json
{
  "status": "OK",
  "timestamp": "2026-03-21T10:30:45.123456",
  "database": {
    "database_exists": true,
    "tables_ok": true,
    "existing_tables": ["dashboard_data", "events"],
    "data_status": {
      "total_records": 500,
      "processed": 450,
      "unprocessed": 50,
      "nlp_completion_percentage": 90.0
    }
  },
  "services": {
    "database": {"status": "OK"},
    "google_apps_script": {"status": "OK"},
    "critical_issues": []
  },
  "nlp": {
    "overall_status": "OK",
    "dependencies": {"nltk": "installed", "transformers": "installed"}
  },
  "pipeline": {
    "overall_status": "HEALTHY",
    "issues": []
  }
}
```

---

## Error Codes & Solutions

### 1. "Database not found"
- Database file missing
- **Fix**: Restore from backup or let app recreate it

### 2. "NLP_SERVICE: transformers missing"
- Missing dependency
- **Fix**: `pip install transformers torch`

### 3. "QUEUE_STUCK"
- Background worker crashed
- **Fix**: Check logs, restart app

### 4. "APPS_SCRIPT_URL invalid"
- Configuration error
- **Fix**: Set correct environment variable

### 5. "Database locked"
- Multiple processes accessing DB
- **Fix**: Kill extra processes or restart

---

## Monitoring Best Practices

### Daily Check
```bash
curl http://your-app:7860/api/diagnostics/health | jq .overall_status
```

### Weekly Review
```bash
curl http://your-app:7860/api/diagnostics/error-log | jq .by_category
```

### Monitor During Upload
```bash
while true; do
  curl -s http://your-app:7860/api/diagnostics/pipeline | jq .pipeline_stages[2].records_with_sentiment
  sleep 10
done
```

---

## Documents

### For Users
- **TROUBLESHOOTING_NLP.md** - Step-by-step guides
- **ERROR_DETECTION_GUIDE.md** - Complete user guide

### For Developers
- **ANALYSIS_ROOT_CAUSE.md** - Technical deep-dive
- **This README** - System documentation

---

## Architecture

```
Request to /api/diagnostics/health
    ↓
Diagnostics Blueprint receives request
    ↓
health_check() function called
    ↓
Creates checkers:
├─ DatabaseChecker
├─ ServiceStatusMonitor
├─ NLPDiagnostics
└─ DataPipelineChecker
    ↓
Each checker runs its full_check() or full_diagnostics()
    ↓
Results aggregated into JSON response
    ↓
Response sent to client (200 OK)
    ↓
Client reviews issues and recommendations
```

---

## Important Files

| File | Purpose | When to Check |
|------|---------|---|
| `logs/app.log` | Application logs | Always, if errors suspected |
| `logs/errors.jsonl` | Structured errors | Automated monitoring |
| `logs/app.log` | Check "DL Worker" | NLP issues |
| `database/dashboard.db` | SQLite database | Schema verification |

---

## Integration Checklist

- [x] Error detection module created
- [x] Diagnostics API routes added
- [x] Blueprints registered in app.py
- [x] Documentation provided
- [ ] (Optional) Add scheduled health checks
- [ ] (Optional) Add alerts on critical errors
- [ ] (Optional) Add Web UI for diagnostics

---

## Troubleshooting The Diagnostics System

### Endpoint returns 404
- Make sure app.py has `app.register_blueprint(diagnostics_bp)`
- Restart app

### Endpoint times out
- Database query slow
- Check database size and index
- Try specific endpoint first (e.g., `/api/diagnostics/services`)

### Missing database table info
- Schema check incomplete
- Run `/api/diagnostics/database` separately

---

## Performance Notes

- Full health check: ~3-5 seconds
- Database check: ~1 second
- NLP diagnostics: ~3-5 seconds (slower due to module import)
- Pipeline check: ~1 second
- Services check: ~2 seconds

Caching these results is not recommended for real-time diagnostics.

---

## Future Enhancements

1. **Web Dashboard**: Visual representation of diagnostics
2. **Alerts**: Send notifications on critical issues
3. **Historical Tracking**: Save diagnostics over time
4. **Auto-Recovery**: Automatically restart failed services
5. **Performance Metrics**: Track response times and system load

---

## Support

For issues with diagnostics system:
1. Check `logs/app.log` for startup errors
2. Verify all modules imported correctly
3. Test individual checkers in isolation
4. Check endpoint responses with curl/postman

