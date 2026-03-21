/**
 * ╔══════════════════════════════════════════════════════════════════╗
 * ║   Alumni Feedback System — Modernized Google Apps Script v3.0   ║
 * ║  Multi-Page | Auto-Webhook | Secure Mapping | Error Tracking     ║
 * ╚══════════════════════════════════════════════════════════════════╝
 */

const CONFIG = {
  SECRET_KEY: PropertiesService.getScriptProperties().getProperty("SECRET_KEY") || "datalens2026",
  WEBHOOK_SECRET: PropertiesService.getScriptProperties().getProperty("WEBHOOK_SECRET") || "webhook-secret-key",
  FORM_PASSWORD: PropertiesService.getScriptProperties().getProperty("FORM_PASSWORD") || "alumni2026",
  DEPARTMENT_OPTIONS: [
    "School of Education & Humanities",
    "School of Engineering: Electronics and Communication",
    "School of Engineering: Mechanical Engineering",
    "School of Engineering: Computer Science & Technology",
    "School of Management & Commerce",
    "School of Engineering",
    "School of Law"
  ]
};

// ─── ENTRY POINTS ────────────────────────────────────────────────────────────

function doPost(e) {
  try {
    if (!e || !e.postData || !e.postData.contents) return _json(false, "Empty body", null, 400);
    const payload = JSON.parse(e.postData.contents);
    if (payload.secret !== CONFIG.SECRET_KEY) return _json(false, "Unauthorized", null, 401);

    const action = (payload.action || "").toLowerCase();
    switch (action) {
      case "create_form": return _handleCreateForm(payload);
      case "get_responses": return _handleGetResponses(payload);
      case "ping": return _json(true, "Alive", { timestamp: new Date().toISOString() });
      default: return _json(false, "Unknown action", null, 404);
    }
  } catch (err) {
    return _json(false, "Server Error", err.message, 500);
  }
}

// ─── ACTION HANDLERS ─────────────────────────────────────────────────────────

function _handleCreateForm(payload) {
  const speaker = payload.speaker_name;
  const date = payload.venue_date;
  const eventId = payload.event_id;
  const webhookUrl = payload.webhook_url;

  if (!speaker || !date) return _json(false, "Speaker and date required", null, 400);

  const form = FormApp.create(`Feedback: ${speaker}`);
  form.setDescription(`Session: ${date} | Speaker: ${speaker}\nJoin us in improving future sessions!`);
  form.setCollectEmail(false);
  form.setAllowResponseEdits(false);
  form.setLimitOneResponsePerUser(false);

  // Section 1: Personal Details
  form.addSectionHeaderItem().setTitle("Step 1: Your Information");
  form.addTextItem().setTitle("Your Full Name").setRequired(true);
  form.addMultipleChoiceItem().setTitle("Department / School").setChoiceValues(CONFIG.DEPARTMENT_OPTIONS).setRequired(true);
  form.addTextItem().setTitle("Roll Number / Student ID").setRequired(true).setHelpText("Example: 2024CS001");

  // Section 3: Feedback
  form.addPageBreakItem().setTitle("Step 3: Session Feedback");
  form.addMultipleChoiceItem()
    .setTitle("Did the session help you gain a better understanding of industry trends or career paths?")
    .setChoiceValues(["Yes, significantly", "To some extent", "Not really"])
    .setRequired(true);
  
  form.addScaleItem().setTitle("Overall session rating?").setBounds(1, 5).setLabels("1 ⭐", "5 ⭐").setRequired(true);

  // Section 4: Qualitative
  form.addPageBreakItem().setTitle("Step 4: Details & Suggestions");
  form.addParagraphTextItem().setTitle("Most valuable aspect of this session?").setRequired(true);
  form.addParagraphTextItem().setTitle("What could be improved?").setRequired(false);
  form.addParagraphTextItem().setTitle("Future topics you want covered?").setRequired(false);

  const formId = form.getId();
  
  // Store metadata for the trigger logic
  const props = PropertiesService.getScriptProperties();
  props.setProperty(`config_${formId}`, JSON.stringify({
    webhook_url: webhookUrl,
    event_id: eventId,
    speaker_name: speaker,
    venue_date: date
  }));

  // Setup Trigger
  ScriptApp.newTrigger('onFormSubmitTrigger').forForm(form).onFormSubmit().create();

  const result = {
    form_id: formId,
    form_url: form.getPublishedUrl(),
    form_edit_url: form.getEditUrl(),
    speaker_name: speaker,
    venue_date: date
  };

  return _json(true, "Form created", result, 201);
}

// ─── TRIGGER LOGIC ───────────────────────────────────────────────────────────

/**
 * Automatically fires when a student submits the Google Form
 */
function onFormSubmitTrigger(e) {
  try {
    const form = e.source;
    const formId = form.getId();
    const props = PropertiesService.getScriptProperties();
    const config = JSON.parse(props.getProperty(`config_${formId}`) || "{}");
    
    if (!config.webhook_url) return;

    const response = e.response;
    const itemResponses = response.getItemResponses();
    const answers = {};
    
    // Map human-readable question titles to backend database keys
    itemResponses.forEach(ir => {
      const q = ir.getItem().getTitle();
      const a = ir.getResponse();
      
      if (q.includes("Full Name")) answers.name_of_student = a;
      else if (q.includes("Department")) answers.department_original = a;
      else if (q.includes("Roll Number")) answers.roll_no_original = a;
      else if (q.includes("helpful")) answers.session_help_understanding = a;
      else if (q.includes("technical")) answers.session_technical_clarity = a;
      else if (q.includes("rating")) answers.session_rating = a;
      else if (q.includes("valuable")) answers.aspect_most_valuable = a;
      else if (q.includes("improved")) answers.improvements_suggestions = a;
      else if (q.includes("topics")) answers.future_topics = a;
    });

    const payload = {
      form_id: formId,
      event_id: config.event_id,
      timestamp: new Date().toISOString(),
      responses: {
        ...answers,
        alumni_speaker_name: config.speaker_name,
        date_of_lecture: config.venue_date
      }
    };

    // Send to Dashboard Webhook
    UrlFetchApp.fetch(config.webhook_url, {
      method: "post",
      contentType: "application/json",
      headers: { "Authorization": "Bearer " + CONFIG.WEBHOOK_SECRET },
      payload: JSON.stringify(payload),
      muteHttpExceptions: true
    });

  } catch (err) {
    console.error("Webhook trigger failed:", err.message);
  }
}

// ─── HELPERS ─────────────────────────────────────────────────────────────────

function _handleGetResponses(payload) {
  const formId = payload.form_id;
  if (!formId) return _json(false, "form_id required", null, 400);

  try {
    const form = FormApp.openById(formId);
    const responses = form.getResponses();
    const result = [];

    responses.forEach(resp => {
      const answers = {
        timestamp: resp.getTimestamp().toISOString()
      };
      
      resp.getItemResponses().forEach(ir => {
        const q = ir.getItem().getTitle();
        const a = ir.getResponse();
        
        if (q.includes("Full Name")) answers.name_of_student = a;
        else if (q.includes("Department")) answers.department_original = a;
        else if (q.includes("Roll Number")) answers.roll_no_original = a;
        else if (q.includes("helpful")) answers.session_help_understanding = a;
        else if (q.includes("technical")) answers.session_technical_clarity = a;
        else if (q.includes("rating")) answers.session_rating = a;
        else if (q.includes("valuable")) answers.aspect_most_valuable = a;
        else if (q.includes("improved")) answers.improvements_suggestions = a;
        else if (q.includes("topics")) answers.future_topics = a;
      });
      result.push(answers);
    });

    return _json(true, "Responses fetched", result);
  } catch (err) {
    return _json(false, "Could not access form", err.message, 404);
  }
}

function _json(success, message, data, code = 200) {
  return ContentService.createTextOutput(JSON.stringify({
    success: success,
    message: message,
    data: data,
    timestamp: new Date().toISOString()
  })).setMimeType(ContentService.MimeType.JSON);
}
