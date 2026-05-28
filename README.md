---
title: DataLens Dashboard
emoji: 📊
colorFrom: indigo
colorTo: purple
sdk: docker
pinned: false
app_port: 7860
---

# DataLens — Project Workflow Documentation

## Architecture Overview

```
User uploads CSV → Browser sends file to Python Flask API → Python processes data → JSON response → Browser renders dashboard
```

### Tech Stack
- **Backend**: Python 3.11 + Flask (API server)
- **Data Processing**: pandas (DataFrames), rapidfuzz (fuzzy string matching)
- **NLP/AI**: TextBlob (sentiment analysis), NLTK (tokenization, stopwords)
- **Frontend**: HTML + CSS + JavaScript + Chart.js
- **Database**: SQLite (persistent storage for admissions data)
- **Admin Panel**: Secure access for data uploads and Google Sheets integration
