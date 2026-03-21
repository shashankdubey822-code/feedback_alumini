# NLP Issue - Quick Troubleshooting Guide

## Problem You Experienced

After uploading data:
1. ✅ All sections work (Overview, Charts, Speakers, Table)
2. ❌ **NLP section is empty** (no sentiment, no keywords)
3. ❌ App sometimes asks for data upload again

---

## Quick Diagnosis

### Step 1: Check System Health
Open your browser and visit:
```
http://your-app:7860/api/diagnostics/health
```

**Look for**:
- `overall_status`: Should be "OK"
- If NOT OK → See "critical_issues" array

### Step 2: Check If Data Was Uploaded
Visit:
```
http://your-app:7860/api/diagnostics/database
```

**Look for**:
- `data_status.total_records`: Should be > 0
- If 0 → Data wasn't uploaded successfully

### Step 3: Check If NLP Is Processing
Visit:
```
http://your-app:7860/api/diagnostics/pipeline
```

**Look for**:
- `unprocessed`: How many records still need NLP?
- `processed`: How many completed?
- `records_with_sentiment`: Should be > 0 eventually

**If stuck**:
- `unprocessed` > 100 and `processed` = 0 → Worker crashed
- `status: "QUEUE_STUCK"` → Worker thread is dead

### Step 4: Check NLP Service
Visit:
```
http://your-app:7860/api/diagnostics/nlp
```

**Look for**:
- `overall_status`: Should be "OK"
- Missing dependencies (transformers, torch, nltk)
- Model loading failures

---

## Common Issues & Fixes

### Issue: "No data" message after upload

**Symptom**: Uploaded data but still see "Upload Required" screen

**Cause**: Background worker is processing (normal)

**Fix**:
1. Wait 30-60 seconds (models are downloading)
2. Refresh the page
3. If still no data after 2 minutes → Worker crashed

**Check**: `GET /api/diagnostics/pipeline`
- If `unprocessed > 0` and `processed = 0` → Worker stuck

---

### Issue: NLP section empty but data exists

**Symptom**: Charts/Tables work, but NLP shows "No sentiment analysis"

**Cause**: API not returning NLP data OR worker crashed

**Fix**:

1. **Check if worker is processing**:
   ```bash
   curl http://your-app:7860/api/diagnostics/pipeline
   ```
   - If `processed > 0` → Data is being processed
   - If `processed = 0` → Worker never started/crashed

2. **Check worker logs**:
   ```bash
   tail -f logs/app.log | grep "DL Worker"
   ```
   - Should show "DL Worker Thread Started"
   - If not → Worker crashed on startup

3. **Check NLP dependencies**:
   ```bash
   curl http://your-app:7860/api/diagnostics/nlp
   ```
   - Look for missing: transformers, torch, NLTK data
   - Fix: `pip install transformers torch`

---

### Issue: All sections work briefly, then NLP disappears

**Symptom**: Dashboard works fine, then when you click NLP tab → Empty

**Cause**: Worker thread crashed mid-process

**Fix**:

1. Check detailed worker errors:
   ```bash
   curl http://your-app:7860/api/diagnostics/nlp
   ```

2. If model loading failed:
   - Check available disk space (DistilBERT is 300MB+)
   - Check internet connection (downloading model)
   - Try: `pip install --upgrade transformers torch`

3. Restart the app
   - Background worker will retry

---

### Issue: Database access errors

**Symptom**: "Database" endpoint fails

**Cause**: Database locked or corrupted

**Fix**:

1. Check database status:
   ```bash
   curl http://your-app:7860/api/diagnostics/database
   ```

2. If database is missing:
   - Copy database from backup OR
   - Delete and let app recreate it

3. If database is locked:
   - Check if multiple processes: `ps aux | grep python`
   - Kill extra processes if needed

---

## How to Monitor Continuously

### Option 1: Check Status Every Minute (CLI)
```bash
watch -n 60 'curl -s http://your-app:7860/api/diagnostics/pipeline | jq .pipeline_stages'
```

### Option 2: Simple Browser Watch
Keep this tab open and refresh every 30s:
```
http://your-app:7860/api/diagnostics/health
```

### Option 3: Log Monitoring
```bash
tail -f logs/app.log
tail -f logs/errors.jsonl
```

---

## What Each Diagnostic Endpoint Shows

| Endpoint | Use Case | Response Time |
|----------|----------|---|
| `/api/diagnostics/health` | **Quick system check** | ~2 seconds |
| `/api/diagnostics/database` | DB schema & data count | ~1 second |
| `/api/diagnostics/nlp` | NLP service status | ~3-5 seconds |
| `/api/diagnostics/pipeline` | Data flow status | ~1 second |
| `/api/diagnostics/services` | All services availability | ~2 seconds |
| `/api/diagnostics/error-log` | Recent errors | ~500ms |

---

## Understanding the Data Pipeline

```
1. DATA INGESTION (Your upload)
   ↓ Upload CSV or Google Sheets
   ↓ Inserted into dashboard_data table
   ↓ Check: /api/diagnostics/pipeline → "total_records"

2. NLP PROCESSING (Background Worker)
   ↓ Worker thread loads AI models (30-60 sec)
   ↓ Analyzes each record's text
   ↓ Stores: dl_sentiment_score, dl_keywords
   ↓ Check: /api/diagnostics/pipeline → "processed" vs "unprocessed"

3. API RESPONSE (Frontend loads)
   ↓ API queries processed sentiment/keywords
   ↓ Returns in /api/data response
   ↓ Frontend renders NLP section

4. FRONTEND DISPLAY
   ↓ Shows sentiment charts/keywords
   ↓ Ready to analyze
   ✓ WORKING!
```

---

## Expected Timings

| Step | Time | Notes |
|------|------|-------|
| CSV Upload | <5 sec | Depends on file size |
| Data Insert | <5 sec | Database write |
| NLP Setup | 10-30 sec | Models loading |
| NLP Processing | 1-2 sec per record | 500 records = 15 min |
| API Response | <1 sec | Query time |
| Frontend Render | <2 sec | JavaScript |

**Total Time**: 30 sec + (records × 2 ms)
- 100 records: ~3-5 minutes
- 500 records: ~15 minutes
- 1000 records: ~30 minutes

---

## When to Check Logs

### If stuck at NLP setup (first 30 seconds)
```bash
grep "DL Worker" logs/app.log
```
Look for:
- "Initializing AI Models..." → Good, loading
- "Error"/exception → Model failed to load

### If stuck at NLP processing
```bash
tail -50 logs/app.log | grep -E "ERROR|processing"
```
Look for:
- "processing X records" → Working
- "Integrity error" → Duplicate in database
- Database timeout → DB is locked

### If worker never started
```bash
grep "start_dl_worker" logs/app.log
```
Should have:
- "DL Worker Thread Started" message
- If not → App startup failed

---

## Recovery Checklist

If NLP section is broken:

- [ ] Visit `/api/diagnostics/health`
- [ ] Read "critical_issues" array
- [ ] Check "recommendations" for next steps
- [ ] Visit `/api/diagnostics/nlp` for specifics
- [ ] Install missing dependencies: `pip install -r requirements.txt`
- [ ] Restart the app
- [ ] Wait 2-3 minutes for background worker
- [ ] Refresh dashboard
- [ ] Check `/api/diagnostics/pipeline` to confirm processing
- [ ] If still empty, check logs for errors

---

## Getting Help

If diagnostics don't help, collect this info:

1. **System Info**:
   ```bash
   curl http://your-app:7860/api/diagnostics/health > system_health.json
   ```

2. **Last 100 lines of logs**:
   ```bash
   tail -100 logs/app.log > app_logs.txt
   tail -100 logs/errors.jsonl > errors.txt
   ```

3. **Database Status**:
   ```bash
   curl http://your-app:7860/api/diagnostics/database > db_status.json
   ```

4. **Paste these files in your issue report**

---

## Pro Tips

💡 **Tip 1**: First 100 records process quickly. Long queues after that are normal.

💡 **Tip 2**: Models cache after first load. Restarts process faster.

💡 **Tip 3**: NLP section updates in real-time as workers finish. No refresh needed.

💡 **Tip 4**: If you see "QUEUE_STUCK", worker thread likely crashed. Check logs first, then restart.

💡 **Tip 5**: Check `/api/diagnostics/health` before assuming something is broken.
