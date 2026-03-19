"""
Google Forms Service — via Google Apps Script.

Instead of calling the Google Forms API directly (which has a known
500 bug with service accounts), this module calls a deployed Google
Apps Script Web App that runs under the user's own Google account.

Environment variable required:
    APPS_SCRIPT_URL = https://script.google.com/macros/s/YOUR_ID/exec
    APPS_SCRIPT_SECRET = datalens2026   (must match the script's SECRET_KEY)
"""

import os
import json
import requests

APPS_SCRIPT_URL    = os.environ.get("APPS_SCRIPT_URL", "")
APPS_SCRIPT_SECRET = os.environ.get("APPS_SCRIPT_SECRET", "datalens2026")

TIMEOUT = 30  # seconds


class AppsScriptError(Exception):
    pass


def _call_script(payload: dict) -> dict:
    """
    POST payload to the Apps Script web app and return the parsed JSON.
    Raises AppsScriptError on any failure.
    """
    if not APPS_SCRIPT_URL:
        raise AppsScriptError(
            "APPS_SCRIPT_URL environment variable is not set. "
            "Deploy the Google Apps Script and paste the web app URL."
        )

    payload["secret"] = APPS_SCRIPT_SECRET

    try:
        response = requests.post(
            APPS_SCRIPT_URL,
            json=payload,
            timeout=TIMEOUT,
            headers={"Content-Type": "application/json"},
        )
        response.raise_for_status()
    except requests.exceptions.Timeout:
        raise AppsScriptError("Request to Apps Script timed out (30s). Try again.")
    except requests.exceptions.ConnectionError as e:
        raise AppsScriptError(f"Could not connect to Apps Script: {e}")
    except requests.exceptions.HTTPError as e:
        raise AppsScriptError(f"HTTP error from Apps Script: {e}")

    try:
        data = response.json()
    except ValueError:
        raise AppsScriptError(
            f"Apps Script did not return JSON. Response: {response.text[:300]}"
        )

    if not data.get("success"):
        raise AppsScriptError(data.get("error", "Unknown error from Apps Script"))

    return data


def ping() -> bool:
    """
    Quick health check — returns True if the Apps Script is reachable.
    """
    try:
        result = _call_script({"action": "ping"})
        return result.get("success", False)
    except AppsScriptError:
        return False


def create_feedback_form(speaker_name: str, venue_date: str) -> dict:
    """
    Ask the Apps Script to create a Google Form.

    Returns:
        {
            "form_id"      : "1ABC...",
            "form_url"     : "https://docs.google.com/forms/d/.../viewform",
            "form_edit_url": "https://docs.google.com/forms/d/.../edit",
        }
    """
    result = _call_script({
        "action"      : "create_form",
        "speaker_name": speaker_name,
        "venue_date"  : venue_date,
    })
    return {
        "form_id"      : result["form_id"],
        "form_url"     : result["form_url"],
        "form_edit_url": result.get("form_edit_url", ""),
    }


def get_form_responses(form_id: str) -> list:
    """
    Fetch all responses for a Google Form via the Apps Script.

    Returns a list of dicts, each with:
        {
            "response_id" : "...",
            "submitted_at": "2026-03-19T...",
            "answers"     : { "question title": "answer", ... },
        }
    """
    result = _call_script({
        "action" : "get_responses",
        "form_id": form_id,
    })
    return result.get("responses", [])


def parse_response_to_submission(response: dict, event_id: int, form_db_id: int) -> dict:
    """
    Convert a raw Apps Script response dict → a dict ready to INSERT
    into the feedback_submissions table.
    """
    answers = response.get("answers", {})
    return {
        "event_id"          : event_id,
        "form_id"           : form_db_id,
        "student_name"      : answers.get("Your Full Name", ""),
        "department"        : answers.get("Department", ""),
        "roll_no"           : answers.get("Roll Number", ""),
        "year"              : answers.get("Year / Semester", ""),
        "helpfulness_rating": _safe_int(answers.get("How helpful was this session?", 0)),
        "valuable_aspect"   : answers.get("What was the most valuable aspect of this session?", ""),
        "improvements"      : answers.get("What could be improved?", ""),
        "future_topics"     : answers.get("What topics would you like covered in future sessions?", ""),
        "raw_answers"       : json.dumps(answers),
        "submitted_at"      : response.get("submitted_at", ""),
    }


def _safe_int(val) -> int:
    try:
        return int(val)
    except (TypeError, ValueError):
        return 0
