import os
import sys
import json
import urllib.request
import urllib.error
from dotenv import load_dotenv

load_dotenv('.env')
key = os.getenv('GEMINI_API_KEY')

# Let's try the exact prompt format from wiki_service.py to see why 400 happens
prompt = """
[SYSTEM INITIALIZATION] 
ROLE: Chief Pedagogical Data Scientist & Alumni Relations Expert
CAPABILITY: Extreme Deep Data Analysis, Psychological Sentiment Profiling, and Actionable Intelligence Synthesis.

You are analyzing raw student survey data from an alumni guest lecture. Do NOT just summarize. You must uncover hidden correlations, diagnose pedagogical friction points (why students struggled or excelled), and generate highly structured, authoritative executive reports.

[SESSION DATA STREAM]
- Target Entity (Speaker): Shatakshi Khanna
- Chronology: 11-11-2025
- Sample Size: 1 student responses
- Quantitative Baseline (Avg Rating): 4.0/5
- Pedagogical Impact Matrix (Understanding Levels): {"Yes": 1}
- High-Value Anchors (What worked): ["good"]
- Friction Points & Critiques (What failed): ["nothing"]
- Forward Trajectory (Requested topics): ["ai"]

[MISSION DIRECTIVE]
Generate THREE high-density intelligence dossiers formatted in strict Markdown. You must liberally use double-bracket WikiLinks (e.g. `[[speakers/safe_speaker]]`, `[[concepts/Advanced_AI]]`, `[[suggestions/Pacing_Control]]`) to weave a massive, interconnected knowledge graph.

1. `events/test.md`:
   - Must contain: Executive Summary, Quantitative Breakdown, Deep Sentiment Analysis, Pedagogical Successes, and Critical Failure Points. Connect all findings to specific student quotes or trends.

2. `speakers/test.md`:
   - Must contain: Speaker Archetype & Style Profile, Aggregate Historical Performance, Core Strengths, and Actionable Directives for their next lecture. If rating is below 3.5, provide a "Risk Mitigation Strategy". 

3. `concepts/New_Concept.md` or `suggestions/New_Critique.md`:
   - Identify the single most critical recurring systemic issue (suggestion) OR the highest-velocity emerging interest (concept). Write an abstract defining this and its impact on the curriculum.

[OUTPUT SCHEMA]
Strict JSON object only. No markdown fences outside the JSON values.
{{
  "event_page": "markdown text for events/test.md",
  "speaker_page": "markdown text for speakers/test.md",
  "new_concept_name": "Name_of_Concept",
  "new_concept_page": "markdown text for concepts/Name_of_Concept.md",
  "new_suggestion_name": "Name_of_Suggestion",
  "new_suggestion_page": "markdown text for suggestions/Name_of_Suggestion.md",
  "speaker_update_summary": "1 sentence executive tl;dr for the speaker's log"
}}
"""

url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={key}"
req_data = json.dumps({
    "contents": [{"parts": [{"text": prompt}]}],
    "generationConfig": {"responseMimeType": "application/json"}
}).encode('utf-8')

req = urllib.request.Request(url, data=req_data, headers={'Content-Type': 'application/json'})

try:
    with urllib.request.urlopen(req) as res:
        print("OK 200")
        print(res.read().decode())
except urllib.error.HTTPError as e:
    print(f"HTTP {e.code}")
    print(e.read().decode())
