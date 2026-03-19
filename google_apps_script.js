/**
 * ============================================================
 * DataLens Feedback System — Google Apps Script Web App
 * ============================================================
 * WHAT IT DOES:
 *   - Runs as YOUR Google account (bypasses service account bug)
 *   - Accepts POST requests from the Flask backend
 *   - Creates Google Forms with 9 fixed questions
 *   - Returns form URL + form ID as JSON
 *
 * HOW TO DEPLOY:
 *   1. Go to script.google.com
 *   2. Click "New Project"
 *   3. Delete all existing code
 *   4. Paste THIS entire file contents
 *   5. Click Deploy > New Deployment
 *   6. Type: Web App
 *   7. Execute as: Me (your Google account)
 *   8. Who has access: Anyone
 *   9. Click Deploy > Copy the Web App URL
 *  10. Paste that URL into your Flask .env as APPS_SCRIPT_URL
 * ============================================================
 */

// ── Security: simple secret key to prevent abuse ─────────────
var SECRET_KEY = "datalens2026";   // <-- Change this to anything you like

// ── Main entry point (called by Flask backend) ────────────────
function doPost(e) {
  try {
    var payload = JSON.parse(e.postData.contents);

    // Verify secret key
    if (payload.secret !== SECRET_KEY) {
      return jsonResponse({ success: false, error: "Unauthorized" }, 403);
    }

    var action = payload.action;

    if (action === "create_form") {
      return handleCreateForm(payload);
    } else if (action === "get_responses") {
      return handleGetResponses(payload);
    } else if (action === "ping") {
      return jsonResponse({ success: true, message: "Apps Script is alive!" });
    } else {
      return jsonResponse({ success: false, error: "Unknown action: " + action }, 400);
    }

  } catch (err) {
    return jsonResponse({ success: false, error: err.toString() }, 500);
  }
}

// ── GET handler (for ping/health check from browser) ─────────
function doGet(e) {
  return jsonResponse({ success: true, message: "DataLens Apps Script is running!" });
}

// ── Action: Create a Google Form ──────────────────────────────
function handleCreateForm(payload) {
  var speakerName = payload.speaker_name;
  var venueDate   = payload.venue_date;

  if (!speakerName || !venueDate) {
    return jsonResponse({ success: false, error: "speaker_name and venue_date are required" }, 400);
  }

  // Create the form
  var form = FormApp.create("Feedback Form: " + speakerName + " | " + venueDate);
  form.setDescription(
    "Please fill in your feedback for the session by " + speakerName + " on " + venueDate + "."
  );
  form.setCollectEmail(false);
  form.setAllowResponseEdits(false);

  // ── Question 1: Speaker Name (read-only info) ────────────
  form.addSectionHeaderItem()
      .setTitle("Session Details")
      .setHelpText("Speaker: " + speakerName + "  |  Date: " + venueDate);

  // ── Question 2: Student Name ─────────────────────────────
  form.addTextItem()
      .setTitle("Your Full Name")
      .setRequired(true);

  // ── Question 3: Department ───────────────────────────────
  var deptItem = form.addListItem();
  deptItem.setTitle("Department")
          .setRequired(true)
          .setChoiceValues([
            "Computer Science",
            "Electronics",
            "Mechanical",
            "Civil",
            "Information Technology",
            "Other"
          ]);

  // ── Question 4: Roll No ──────────────────────────────────
  form.addTextItem()
      .setTitle("Roll Number")
      .setRequired(true);

  // ── Question 5: Year / Semester ──────────────────────────
  var yearItem = form.addListItem();
  yearItem.setTitle("Year / Semester")
          .setRequired(true)
          .setChoiceValues(["1st Year", "2nd Year", "3rd Year", "4th Year"]);

  // ── Question 6: Helpfulness Rating ──────────────────────
  var ratingItem = form.addScaleItem();
  ratingItem.setTitle("How helpful was this session?")
            .setLabels("Not helpful at all", "Extremely helpful")
            .setBounds(1, 5)
            .setRequired(true);

  // ── Question 7: Most Valuable Aspect ────────────────────
  form.addParagraphTextItem()
      .setTitle("What was the most valuable aspect of this session?")
      .setRequired(true);

  // ── Question 8: Improvements ────────────────────────────
  form.addParagraphTextItem()
      .setTitle("What could be improved?")
      .setRequired(false);

  // ── Question 9: Future Topics ────────────────────────────
  form.addParagraphTextItem()
      .setTitle("What topics would you like covered in future sessions?")
      .setRequired(false);

  // Get the published form URL (for students to fill)
  var formUrl      = form.getPublishedUrl();
  var formId       = form.getId();
  var formEditUrl  = form.getEditUrl();

  return jsonResponse({
    success      : true,
    form_id      : formId,
    form_url     : formUrl,
    form_edit_url: formEditUrl,
    speaker_name : speakerName,
    venue_date   : venueDate,
    message      : "Form created successfully"
  });
}

// ── Action: Get form responses ────────────────────────────────
function handleGetResponses(payload) {
  var formId = payload.form_id;
  if (!formId) {
    return jsonResponse({ success: false, error: "form_id is required" }, 400);
  }

  try {
    var form      = FormApp.openById(formId);
    var responses = form.getResponses();
    var items     = form.getItems();
    var result    = [];

    for (var i = 0; i < responses.length; i++) {
      var resp    = responses[i];
      var itemMap = {};
      var itemResponses = resp.getItemResponses();

      for (var j = 0; j < itemResponses.length; j++) {
        var ir = itemResponses[j];
        itemMap[ir.getItem().getTitle()] = ir.getResponse();
      }

      result.push({
        response_id  : resp.getId(),
        submitted_at : resp.getTimestamp().toISOString(),
        answers      : itemMap
      });
    }

    return jsonResponse({
      success        : true,
      form_id        : formId,
      response_count : result.length,
      responses      : result
    });

  } catch (err) {
    return jsonResponse({ success: false, error: "Could not open form: " + err.toString() }, 500);
  }
}

// ── Helper: Build a JSON ContentService response ─────────────
function jsonResponse(obj) {
  return ContentService
    .createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}
