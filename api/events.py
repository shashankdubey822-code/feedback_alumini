import json
import sqlite3
from flask import Blueprint, request, jsonify

from utils.db_init import get_db
from services.google_forms_service import (
    create_feedback_form,
    get_form_responses,
    parse_response_to_submission,
    ping as ping_script,
    toggle_form_status,
    AppsScriptError,
)

events_bp = Blueprint("events", __name__)

# ── Helper: check admin token (matches app.js Bearer token pattern) ──
def _check_admin(req):
    """Returns True if the request has a valid admin Bearer token."""
    auth = req.headers.get("Authorization", "")
    return auth == "Bearer admin_stateless_token"


# ─────────────────────────────────────────────────────────────
# POST /api/admin/create-event
# Body: { "speaker_name": "...", "venue_date": "YYYY-MM-DD" }
# ─────────────────────────────────────────────────────────────
@events_bp.route("/api/admin/create-event", methods=["POST"])
def create_event():
    if not _check_admin(request):
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    data = request.get_json(force=True) or {}
    speaker_name = (data.get("speaker_name") or "").strip()
    venue_date   = (data.get("venue_date")   or "").strip()

    if not speaker_name or not venue_date:
        return jsonify({"success": False, "error": "speaker_name and venue_date are required"}), 400

    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO events (speaker_name, venue_date) VALUES (?, ?)",
            (speaker_name, venue_date),
        )
        conn.commit()
        event_id = cursor.lastrowid
        conn.close()

        return jsonify({
            "success" : True,
            "event_id": event_id,
            "message" : "Event created successfully",
        })

    except sqlite3.Error as e:
        return jsonify({"success": False, "error": f"Database error: {e}"}), 500


# ─────────────────────────────────────────────────────────────
# POST /api/admin/generate-form
# Body: { "event_id": 1 }
# ─────────────────────────────────────────────────────────────
@events_bp.route("/api/admin/generate-form", methods=["POST"])
def generate_form():
    if not _check_admin(request):
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    data     = request.get_json(force=True) or {}
    event_id = data.get("event_id")

    if not event_id:
        return jsonify({"success": False, "error": "event_id is required"}), 400

    try:
        conn   = get_db()
        cursor = conn.cursor()

        # Fetch event
        cursor.execute("SELECT * FROM events WHERE id = ?", (event_id,))
        event = cursor.fetchone()
        if not event:
            conn.close()
            return jsonify({"success": False, "error": f"Event {event_id} not found"}), 404

        # Check if form already created
        cursor.execute(
            "SELECT * FROM feedback_forms WHERE event_id = ?", (event_id,)
        )
        existing = cursor.fetchone()
        if existing:
            conn.close()
            return jsonify({
                "success" : True,
                "form_id" : existing["google_form_id"],
                "form_url": existing["google_form_url"],
                "message" : "Form already exists for this event",
            })

        # Create the Google Form via Apps Script
        # Build webhook URL dynamically based on current host
        scheme = request.headers.get("X-Forwarded-Proto", request.scheme)
        webhook_url = f"{scheme}://{request.host}/api/webhook/google-submit"

        try:
            form_data = create_feedback_form(
                speaker_name=event["speaker_name"],
                venue_date=event["venue_date"],
                webhook_url=webhook_url,
                event_id=event_id
            )
        except AppsScriptError as e:
            conn.close()
            return jsonify({"success": False, "error": f"Google Forms error: {e}"}), 502

        # Save form record to DB
        cursor.execute(
            """INSERT INTO feedback_forms
               (event_id, google_form_id, google_form_url, google_edit_url)
               VALUES (?, ?, ?, ?)""",
            (
                event_id,
                form_data["form_id"],
                form_data["form_url"],
                form_data.get("form_edit_url", ""),
            ),
        )
        conn.commit()
        conn.close()

        return jsonify({
            "success" : True,
            "form_id" : form_data["form_id"],
            "form_url": form_data["form_url"],
            "message" : "Form generated successfully",
        })

    except sqlite3.Error as e:
        return jsonify({"success": False, "error": f"Database error: {e}"}), 500


# ─────────────────────────────────────────────────────────────
# GET /api/feedback-form?event_id=1
# ─────────────────────────────────────────────────────────────
@events_bp.route("/api/feedback-form", methods=["GET"])
def get_feedback_form():
    event_id = request.args.get("event_id")
    if not event_id:
        return jsonify({"success": False, "error": "event_id query param required"}), 400

    try:
        conn   = get_db()
        cursor = conn.cursor()
        cursor.execute(
            """SELECT e.speaker_name, e.venue_date, f.google_form_id, f.google_form_url
               FROM events e
               JOIN feedback_forms f ON f.event_id = e.id
               WHERE e.id = ?""",
            (event_id,),
        )
        row = cursor.fetchone()
        conn.close()

        if not row:
            return jsonify({"success": False, "error": "No form found for this event"}), 404

        return jsonify({
            "success"     : True,
            "event_id"    : event_id,
            "speaker_name": row["speaker_name"],
            "venue_date"  : row["venue_date"],
            "form_id"     : row["google_form_id"],
            "form_url"    : row["google_form_url"],
        })

    except sqlite3.Error as e:
        return jsonify({"success": False, "error": f"Database error: {e}"}), 500


# ─────────────────────────────────────────────────────────────
# POST /api/admin/sync-responses
# Body: { "event_id": 1 }
# ─────────────────────────────────────────────────────────────
@events_bp.route("/api/admin/sync-responses", methods=["POST"])
def sync_responses():
    if not _check_admin(request):
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    data     = request.get_json(force=True) or {}
    event_id = data.get("event_id")

    if not event_id:
        return jsonify({"success": False, "error": "event_id is required"}), 400

    try:
        conn   = get_db()
        cursor = conn.cursor()

        # Get the form record
        cursor.execute(
            "SELECT * FROM feedback_forms WHERE event_id = ?", (event_id,)
        )
        form_record = cursor.fetchone()
        if not form_record:
            conn.close()
            return jsonify({"success": False, "error": "No form found for this event — generate it first"}), 404

        form_db_id     = form_record["id"]
        google_form_id = form_record["google_form_id"]

        # Fetch responses from Google via Apps Script
        try:
            responses = get_form_responses(google_form_id)
        except AppsScriptError as e:
            conn.close()
            return jsonify({"success": False, "error": f"Could not fetch responses: {e}"}), 502

        # Only insert responses we haven't seen yet
        synced = 0
        for resp in responses:
            submission = parse_response_to_submission(resp, event_id, form_db_id)

            # Avoid duplicates by checking submitted_at + roll_no
            cursor.execute(
                "SELECT id FROM feedback_submissions WHERE event_id=? AND roll_no=? AND submitted_at=?",
                (event_id, submission["roll_no"], submission["submitted_at"]),
            )
            if cursor.fetchone():
                continue  # already synced

            cursor.execute(
                """INSERT INTO feedback_submissions
                   (event_id, form_id, student_name, department, roll_no, year,
                    helpfulness_rating, valuable_aspect, improvements, future_topics,
                    raw_answers, submitted_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    submission["event_id"],
                    submission["form_id"],
                    submission["student_name"],
                    submission["department"],
                    submission["roll_no"],
                    submission["year"],
                    submission["helpfulness_rating"],
                    submission["valuable_aspect"],
                    submission["improvements"],
                    submission["future_topics"],
                    submission["raw_answers"],
                    submission["submitted_at"],
                ),
            )
            synced += 1

        conn.commit()
        conn.close()

        return jsonify({
            "success"         : True,
            "responses_synced": synced,
            "total_responses" : len(responses),
            "message"         : f"Synced {synced} new response(s)",
        })

    except sqlite3.Error as e:
        return jsonify({"success": False, "error": f"Database error: {e}"}), 500


# ─────────────────────────────────────────────────────────────
# GET /api/admin/events
# ─────────────────────────────────────────────────────────────
@events_bp.route("/api/admin/events", methods=["GET"])
def list_events():
    if not _check_admin(request):
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    try:
        conn   = get_db()
        cursor = conn.cursor()
        cursor.execute(
            """SELECT e.id, e.speaker_name, e.venue_date, e.created_at,
                      f.google_form_url, f.google_form_id,
                      (SELECT COUNT(*) FROM feedback_submissions s WHERE s.event_id = e.id) as response_count
               FROM events e
               LEFT JOIN feedback_forms f ON f.event_id = e.id
               ORDER BY e.created_at DESC"""
        )
        rows = cursor.fetchall()
        conn.close()

        events = []
        for row in rows:
            events.append({
                "id"            : row["id"],
                "speaker_name"  : row["speaker_name"],
                "venue_date"    : row["venue_date"],
                "form_url"      : row["google_form_url"],
                "form_id"       : row["google_form_id"],
                "responses"     : row["response_count"],
                "created_at"    : row["created_at"],
            })

        return jsonify({"success": True, "events": events})

    except sqlite3.Error as e:
        return jsonify({"success": False, "error": f"Database error: {e}"}), 500


# ─────────────────────────────────────────────────────────────
# GET /api/admin/ping-script
# Quick health check: is the Apps Script reachable?
# ─────────────────────────────────────────────────────────────
@events_bp.route("/api/admin/ping-script", methods=["GET"])
def ping_apps_script():
    ok = ping_script()
    return jsonify({
        "success": ok,
        "message": "Apps Script is reachable" if ok else "Apps Script is NOT reachable — check APPS_SCRIPT_URL",
    })


# ─────────────────────────────────────────────────────────────
# POST /api/admin/toggle-form
# Body: { "form_id": "...", "accepting_responses": bool (optional) }
# ─────────────────────────────────────────────────────────────
@events_bp.route("/api/admin/toggle-form", methods=["POST"])
def admin_toggle_form():
    if not _check_admin(request):
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    data = request.get_json(force=True) or {}
    form_id = data.get("form_id")
    accepting = data.get("accepting_responses")

    if not form_id:
        return jsonify({"success": False, "error": "form_id required"}), 400

    try:
        new_status = toggle_form_status(form_id, accepting)
        return jsonify({
            "success": True,
            "accepting_responses": new_status,
            "message": "Form toggled successfully"
        })
    except AppsScriptError as e:
        return jsonify({"success": False, "error": str(e)}), 502


# ─────────────────────────────────────────────────────────────
# POST /api/webhook/google-submit
# ─────────────────────────────────────────────────────────────
@events_bp.route("/api/webhook/google-submit", methods=["POST"])
def webhook_google_submit():
    data = request.get_json(force=True) or {}
    
    # Simple verification using a shared secret
    from services.google_forms_service import APPS_SCRIPT_SECRET
    if data.get("secret") != APPS_SCRIPT_SECRET:
        return jsonify({"success": False, "error": "Unauthorized webhook"}), 403

    event_id = data.get("event_id")
    response_data = data.get("response_data", {})
    if not event_id or not response_data:
        return jsonify({"success": False, "error": "Invalid payload"}), 400

    try:
        conn = get_db()
        cursor = conn.cursor()

        # Find the form DB ID
        cursor.execute("SELECT id FROM feedback_forms WHERE event_id = ?", (event_id,))
        form_record = cursor.fetchone()
        if not form_record:
            conn.close()
            return jsonify({"success": False, "error": "Form not found"}), 404
            
        form_db_id = form_record["id"]

        # Parse live webhook response into normal submission format
        submission = parse_response_to_submission(response_data, event_id, form_db_id)

        # Check for duplicates (webhook retries)
        cursor.execute(
            "SELECT id FROM feedback_submissions WHERE event_id=? AND roll_no=? AND submitted_at=?",
            (event_id, submission["roll_no"], submission["submitted_at"]),
        )
        if not cursor.fetchone():
            cursor.execute(
                """INSERT INTO feedback_submissions
                   (event_id, form_id, student_name, department, roll_no, year,
                    helpfulness_rating, valuable_aspect, improvements, future_topics,
                    raw_answers, submitted_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    submission["event_id"], submission["form_id"],
                    submission["student_name"], submission["department"],
                    submission["roll_no"], submission["year"],
                    submission["helpfulness_rating"], submission["valuable_aspect"],
                    submission["improvements"], submission["future_topics"],
                    submission["raw_answers"], submission["submitted_at"],
                )
            )
            conn.commit()

        conn.close()
        return jsonify({"success": True, "message": "Webhook processed"})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ─────────────────────────────────────────────────────────────
# POST /api/admin/terminate-all-forms
# Closes EVERY Google Form registered in the DB at once.
# ─────────────────────────────────────────────────────────────
@events_bp.route("/api/admin/terminate-all-forms", methods=["POST"])
def terminate_all_forms():
    if not _check_admin(request):
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    try:
        conn   = get_db()
        cursor = conn.cursor()

        # Fetch every form_id that has ever been created
        cursor.execute("SELECT google_form_id FROM feedback_forms WHERE google_form_id IS NOT NULL")
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            return jsonify({"success": True, "closed": 0, "message": "No forms found to terminate."})

        # Call Apps Script terminate_all action — it will close all forms simultaneously
        from services.google_forms_service import _call_script, AppsScriptError
        try:
            result = _call_script({"action": "terminate_all"})
        except AppsScriptError as e:
            return jsonify({"success": False, "error": f"Apps Script error: {e}"}), 502

        return jsonify({
            "success": True,
            "closed" : result.get("closed", 0),
            "total"  : result.get("total",  0),
            "message": result.get("message", "All forms terminated"),
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
