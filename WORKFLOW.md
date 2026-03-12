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
- **No database** — everything is in-memory per session

---

## File-by-File Workflow

### 1. `app.py` — Python Backend (Flask Server)

**Startup Flow:**
1. Flask app starts on `http://localhost:5000`
2. NLTK downloads `punkt_tab` and `stopwords` data if missing
3. Custom stop words list is loaded (na, nil, none, nothing, no, nope, etc.)
4. Static files (HTML, CSS, JS) are served from the same directory

**API Endpoint: `POST /api/upload`**
1. Receives CSV file from browser via `multipart/form-data`
2. Reads file content as UTF-8 string
3. Parses CSV into a pandas DataFrame
4. Drops fully empty rows, fills NaN with empty string, strips whitespace
5. **Column Type Detection** (`detect_column_types`):
   - Checks each column's values (ignoring NA, N/A, -, .)
   - Tests for date patterns → type = `date`
   - Tests if >50% values are numeric → type = `numeric`
   - Tests unique count (≤30 or <40% ratio) → type = `categorical`
   - Else → type = `text`
6. **Fuzzy Department Normalization** (`fuzzy_normalize`):
   - For columns detected as categorical AND matching department keywords
   - Uses `rapidfuzz.fuzz.token_sort_ratio` to compare all values
   - Groups similar strings (threshold: 65% similarity)
   - Most frequent member becomes the canonical name
   - Creates a new column `<original> (Normalized)` in the DataFrame
7. **Analytics Builder** (`build_analytics`):
   - Calls all analytics sub-functions and assembles JSON response
8. Returns JSON with: `meta`, `kpis`, `charts`, `sentiment`, `keywords`, `crossTabs`, `timeTrends`, `speakerStats`, `tableData`, `filters`

**Analytics Sub-Functions:**

| Function | What It Does |
|----------|-------------|
| `build_kpis()` | Calculates KPI metrics: total records, column count, avg/min/max/median for numeric, unique counts for categorical, date ranges |
| `build_chart_data()` | Generates chart data (labels + counts) for categorical (bar/doughnut) and numeric (histogram) columns |
| `build_sentiment()` | Runs TextBlob on each text value → polarity (-1 to +1) and subjectivity (0 to 1), groups into positive/neutral/negative |
| `build_keywords()` | Tokenizes text, removes stopwords, counts word frequency, returns top 30 per column |
| `build_cross_tabs()` | Groups numeric columns by categorical columns → calculates group means and counts |
| `build_time_trends()` | Groups data by month → counts responses and calculates monthly average ratings |
| `build_speaker_stats()` | Finds speaker-like columns, calculates per-speaker: response count, avg ratings, avg sentiment |
| `build_filter_options()` | Extracts unique values for dropdowns (categorical), unique dates for date pickers |
| `build_table_data()` | Converts DataFrame rows to JSON list (max 500 rows) |

**API Endpoint: `POST /api/filter`**
1. Receives JSON with `{ filters: { column: value }, search: "..." }`
2. Starts from original DataFrame, re-applies normalizations
3. Applies global text search across all columns
4. Applies per-column filters (categorical exact match, text contains, numeric comparison, date range)
5. Re-runs all analytics on filtered data
6. Returns updated JSON

---

### 2. `index.html` — Frontend Structure

**Two Main Screens:**
1. **Upload Screen** (`#upload-screen`): Drag-and-drop zone + Browse Files button
2. **Dashboard Screen** (`#dashboard-screen`): Sidebar + Main Content

**Dashboard has 5 navigable sections:**
1. **Overview** (`#overview-section`): KPI cards grid + Filters panel
2. **Charts** (`#charts-section`): Distribution charts + Cross-tab charts + Time trend charts
3. **NLP Insights** (`#nlp-section`): Sentiment analysis cards + Keyword clouds
4. **Speakers** (`#speakers-section`): Speaker cards + Speaker comparison charts
5. **Data Table** (`#table-section`): Sortable, paginated data table

---

### 3. `app.js` — Frontend Logic

**Startup:** Sets up file upload handlers, sidebar navigation, dashboard button handlers

**Upload Flow:**
1. User selects/drops file → `handleFile()` called
2. Creates `FormData`, sends `POST /api/upload` to Python
3. Shows progress bar with status messages
4. On response: stores analytics in `state`, switches to dashboard, calls `renderDashboard()`

**Render Flow:**
1. `renderKPIs()` — injects KPI cards into grid
2. `renderFilters()` — builds filter controls (dropdowns, text inputs) from Python's filter metadata
3. `renderCharts()` — creates Chart.js instances (bar, doughnut) for each chart in response
4. `renderCrossTabs()` — horizontal/vertical bar charts for avg rating by category
5. `renderTimeTrends()` — line charts with area fill for monthly trends
6. `renderSentiment()` — sentiment cards with canvas gauge (arc drawing), polarity bars
7. `renderKeywords()` — word cloud using styled span tags with size proportional to frequency
8. `renderSpeakers()` — speaker cards with avatar, stats, sentiment pill + comparison bar charts
9. `renderTable()` — table head (sortable), body (paginated), pagination buttons

**Filter Flow:**
1. User changes any filter → `applyFilters()` debounced (400ms)
2. Collects all filter values from DOM, sends `POST /api/filter` to Python
3. Re-renders all sections with new data (except filter controls themselves)

**Sidebar Navigation:**
- Click nav item → hides all `.dashboard-section`, shows targeted section
- Mobile: toggle button slides sidebar in/out

---

### 4. `style.css` — Design System

**Color Variables:** Deep dark palette (#080a10 base), purple/indigo accents, semantic colors (emerald=positive, amber=neutral, rose=negative)

**Layout:** Fixed sidebar (220px) + scrollable main content + sticky topbar

**Components:** KPI cards (gradient top borders, hover lift), chart cards (glassmorphism), sentiment gauges (CSS + canvas), word cloud tags (pill-shaped, colored), speaker cards (avatar circles, stat rows), data table (sticky thead, hover highlight)

**Animations:** Staggered entry (`countUp` with delays), floating brand icon, gradient shimmer on title, progress bar shimmer

---

### 5. `sample_data.csv` — Input Data

**Source:** Google Forms survey for alumni guest lectures at Manav Rachna Education Institutions

**11 Columns:** Timestamp, Name of Student, Department, Roll No., Date of the Lecture, Alumni Speaker Name, Helpfulness Question, Most Valuable Aspect, Rating (1-5), Improvement Suggestions, Future Topics

**44 Rows** spanning Nov 2025 – Feb 2026

---

## How to Run

```bash
# 1. Install dependencies (one-time)
pip install flask flask-cors pandas rapidfuzz textblob nltk

# 2. Start the server
python app.py

# 3. Open in browser
# http://localhost:5000

# 4. Upload sample_data.csv (or any other CSV)
```
