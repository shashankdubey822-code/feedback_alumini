/**
 * ╔══════════════════════════════════════════════════════════════╗
 * ║       DataLens Feedback System — Google Apps Script          ║
 * ╚══════════════════════════════════════════════════════════════╝
 *
 * DEPLOYMENT STEPS (do this once, then again if you change code):
 *   1. Paste this entire file into script.google.com
 *   2. In the toolbar, select "authorizeScript" in the dropdown → click Run
 *      (You MUST click Allow in the popup that appears — only once ever!)
 *   3. Click Deploy → Manage Deployments → Edit (pencil icon)
 *   4. Under Version, choose "New version" → click Deploy
 *   5. Copy the Web App URL → paste it as APPS_SCRIPT_URL in HF Secrets
 *
 * SUPPORTED ACTIONS (sent as POST from Python backend):
 *   • create_form       – Creates a new Google Form for a speaker/event
 *   • toggle_form       – Opens or closes ONE specific form
 *   • terminate_all     – Closes ALL forms managed by this script at once
 *   • get_responses     – Returns all responses for a given form
 *   • ping              – Health check; returns {success:true}
 */

// ─── Config ───────────────────────────────────────────────────────────────────
var SECRET_KEY = "datalens2026"; // Must match APPS_SCRIPT_SECRET in HF Secrets

// ─── Entry point ──────────────────────────────────────────────────────────────
function doPost(e) {
  try {
    if (!e || !e.postData || !e.postData.contents) {
      return _json({ success: false, error: "Empty request body" });
    }

    var payload;
    try {
      payload = JSON.parse(e.postData.contents);
    } catch (parseErr) {
      return _json({ success: false, error: "Invalid JSON: " + parseErr.message });
    }

    // Security check
    if (!payload.secret || payload.secret !== SECRET_KEY) {
      return _json({ success: false, error: "Unauthorized — wrong secret key" });
    }

    var action = (payload.action || "").trim();

    if      (action === "create_form"   ) return _createForm(payload);
    else if (action === "toggle_form"   ) return _toggleForm(payload);
    else if (action === "terminate_all" ) return _terminateAll(payload);
    else if (action === "get_responses" ) return _getResponses(payload);
    else if (action === "ping"          ) return _json({ success: true, message: "Apps Script is alive!" });
    else return _json({ success: false, error: "Unknown action: " + action });

  } catch (err) {
    return _json({ success: false, error: "Unhandled error: " + err.message });
  }
}

// ─── GET handler (browser health check) ──────────────────────────────────────
function doGet(e) {
  return _json({ success: true, message: "DataLens Apps Script is running!" });
}

// ─── ONE-TIME SETUP: Run this manually ONCE to grant OAuth permissions ────────
// Instructions: Select "authorizeScript" in the toolbar dropdown → click Run
// Click "Allow" in the popup → done!
function authorizeScript() {
  // Touching ScriptApp forces Google to request the script.scriptapp permission
  var existing = ScriptApp.getProjectTriggers();
  Logger.log("✅ Authorization successful! Existing triggers: " + existing.length);
  Logger.log("You can now deploy and use the dashboard without any permission errors.");
}

// ═══════════════════════════════════════════════════════════════════════════════
//  ACTION HANDLERS
// ═══════════════════════════════════════════════════════════════════════════════

// ─── Create Form ──────────────────────────────────────────────────────────────
function _createForm(payload) {
  var speakerName = (payload.speaker_name || "").trim();
  var venueDate   = (payload.venue_date   || "").trim();
  var webhookUrl  = (payload.webhook_url  || "").trim();
  var eventId     = payload.event_id;

  if (!speakerName) return _json({ success: false, error: "speaker_name is required" });
  if (!venueDate)   return _json({ success: false, error: "venue_date is required" });

  try {
    var form = FormApp.create("Feedback: " + speakerName);
    form.setDescription(
      "Please share your feedback for the session held on " + venueDate + ".\n" +
      "Your responses help us improve future events!"
    );
    form.setCollectEmail(false);
    form.setLimitOneResponsePerUser(false);

    // Q1 — Name
    form.addTextItem().setTitle("Your Full Name").setRequired(true);

    // Q2 — Department
    form.addMultipleChoiceItem()
        .setTitle("Department / School")
        .setChoiceValues([
          "School of Computer Applications (SCA)",
          "School of Engineering (SOE)",
          "School of Management (SOM)",
          "School of Design (SOD)",
          "Other"
        ])
        .setRequired(true);

    // Q3 — Roll Number
    form.addTextItem().setTitle("Roll Number / Student ID").setRequired(true);

    // Q4 — Year
    form.addMultipleChoiceItem()
        .setTitle("Year / Semester")
        .setChoiceValues(["1st Year", "2nd Year", "3rd Year", "4th Year", "Alumni / Faculty"])
        .setRequired(true);

    // Q5 — Helpfulness scale
    form.addScaleItem()
        .setTitle("How helpful was this session for your understanding?")
        .setBounds(1, 5)
        .setLabels("Not Helpful at All", "Extremely Helpful")
        .setRequired(true);

    // Q6 — Technical clarity scale
    form.addScaleItem()
        .setTitle("How clear were the technical explanations?")
        .setBounds(1, 5)
        .setLabels("Very Unclear", "Very Clear")
        .setRequired(true);

    // Q7 — Most valuable aspect
    form.addParagraphTextItem()
        .setTitle("What was the most valuable aspect of this session?")
        .setRequired(true);

    // Q8 — What could be improved
    form.addParagraphTextItem()
        .setTitle("What could be improved?")
        .setRequired(false);

    // Q9 — Future topics
    form.addParagraphTextItem()
        .setTitle("What topics would you like covered in future sessions?")
        .setRequired(false);

    var formId = form.getId();

    // Store all form IDs managed by this script (for terminate_all)
    _registerFormId(formId);

    // Attach real-time webhook trigger if requested
    if (webhookUrl && eventId) {
      PropertiesService.getScriptProperties()
          .setProperty("webhook_" + formId, webhookUrl);
      PropertiesService.getScriptProperties()
          .setProperty("event_" + formId, String(eventId));

      // Only create if trigger does not already exist for this form
      var triggers = ScriptApp.getProjectTriggers();
      var alreadyExists = false;
      for (var i = 0; i < triggers.length; i++) {
        if (triggers[i].getTriggerSourceId() === formId) {
          alreadyExists = true;
          break;
        }
      }
      if (!alreadyExists) {
        ScriptApp.newTrigger("onFormSubmitTrigger")
            .forForm(form)
            .onFormSubmit()
            .create();
      }
    }

    return _json({
      success      : true,
      form_id      : formId,
      form_url     : form.getPublishedUrl(),
      form_edit_url: form.getEditUrl(),
      message      : "Form created successfully"
    });

  } catch (err) {
    return _json({ success: false, error: "Could not create form: " + err.message });
  }
}

// ─── Toggle one Form ──────────────────────────────────────────────────────────
function _toggleForm(payload) {
  var formId = (payload.form_id || "").trim();
  if (!formId) return _json({ success: false, error: "form_id is required" });

  try {
    var form = FormApp.openById(formId);
    var currentState = form.isAcceptingResponses();

    // If accepting_responses is explicitly provided, use it; otherwise just flip
    var newState;
    if (payload.accepting_responses !== undefined && payload.accepting_responses !== null) {
      newState = Boolean(payload.accepting_responses);
    } else {
      newState = !currentState;
    }

    form.setAcceptingResponses(newState);
    var finalState = form.isAcceptingResponses();

    return _json({
      success             : true,
      form_id             : formId,
      accepting_responses : finalState,
      message             : "Form is now " + (finalState ? "OPEN ✅" : "CLOSED 🔒")
    });

  } catch (err) {
    return _json({ success: false, error: "Could not toggle form: " + err.message });
  }
}

// ─── Terminate ALL forms ──────────────────────────────────────────────────────
function _terminateAll(payload) {
  try {
    var allFormIds = _getAllFormIds();
    if (allFormIds.length === 0) {
      return _json({ success: true, closed: 0, message: "No forms registered — nothing to close." });
    }

    var closed = 0;
    var errors = [];

    for (var i = 0; i < allFormIds.length; i++) {
      var fid = allFormIds[i];
      try {
        var form = FormApp.openById(fid);
        form.setAcceptingResponses(false);
        closed++;
      } catch (e) {
        errors.push(fid + ": " + e.message);
      }
    }

    return _json({
      success : true,
      closed  : closed,
      total   : allFormIds.length,
      errors  : errors,
      message : "🔒 " + closed + " of " + allFormIds.length + " forms have been CLOSED. No further submissions accepted."
    });

  } catch (err) {
    return _json({ success: false, error: "terminate_all failed: " + err.message });
  }
}

// ─── Get form responses ───────────────────────────────────────────────────────
function _getResponses(payload) {
  var formId = (payload.form_id || "").trim();
  if (!formId) return _json({ success: false, error: "form_id is required" });

  try {
    var form      = FormApp.openById(formId);
    var responses = form.getResponses();
    var result    = [];

    for (var i = 0; i < responses.length; i++) {
      var resp         = responses[i];
      var itemMap      = {};
      var itemResps    = resp.getItemResponses();
      for (var j = 0; j < itemResps.length; j++) {
        var ir = itemResps[j];
        itemMap[ir.getItem().getTitle()] = ir.getResponse();
      }
      result.push({
        response_id  : resp.getId(),
        submitted_at : resp.getTimestamp().toISOString(),
        answers      : itemMap
      });
    }

    return _json({
      success        : true,
      form_id        : formId,
      response_count : result.length,
      responses      : result
    });

  } catch (err) {
    return _json({ success: false, error: "Could not fetch responses: " + err.message });
  }
}

// ─── Real-time Webhook trigger ────────────────────────────────────────────────
function onFormSubmitTrigger(e) {
  try {
    var form   = e.source;
    var formId = form.getId();

    var webhookUrl = PropertiesService.getScriptProperties().getProperty("webhook_" + formId);
    var eventIdStr = PropertiesService.getScriptProperties().getProperty("event_"   + formId);

    if (!webhookUrl || !eventIdStr) {
      Logger.log("No webhook URL or event_id found for form: " + formId);
      return;
    }

    var response      = e.response;
    var itemResponses = response.getItemResponses();
    var itemMap       = {};

    for (var i = 0; i < itemResponses.length; i++) {
      var ir = itemResponses[i];
      itemMap[ir.getItem().getTitle()] = ir.getResponse();
    }

    var postPayload = {
      secret   : SECRET_KEY,
      event_id : parseInt(eventIdStr, 10),
      response_data: {
        response_id  : response.getId(),
        submitted_at : response.getTimestamp().toISOString(),
        answers      : itemMap
      }
    };

    UrlFetchApp.fetch(webhookUrl, {
      method      : "post",
      contentType : "application/json",
      payload     : JSON.stringify(postPayload),
      muteHttpExceptions: true
    });

  } catch (err) {
    Logger.log("Webhook trigger error: " + err.message);
  }
}

// ═══════════════════════════════════════════════════════════════════════════════
//  INTERNAL HELPERS
// ═══════════════════════════════════════════════════════════════════════════════

// Keep a registry of all form IDs so terminate_all knows what to close
function _registerFormId(formId) {
  var props   = PropertiesService.getScriptProperties();
  var allJson = props.getProperty("all_form_ids") || "[]";
  var all     = JSON.parse(allJson);
  if (all.indexOf(formId) === -1) {
    all.push(formId);
    props.setProperty("all_form_ids", JSON.stringify(all));
  }
}

function _getAllFormIds() {
  var props   = PropertiesService.getScriptProperties();
  var allJson = props.getProperty("all_form_ids") || "[]";
  try {
    return JSON.parse(allJson);
  } catch (e) {
    return [];
  }
}

// Unified JSON response builder
function _json(obj) {
  return ContentService
      .createTextOutput(JSON.stringify(obj))
      .setMimeType(ContentService.MimeType.JSON);
}
