/**
 * ╔══════════════════════════════════════════════════════════════════╗
 * ║   Alumni Feedback System — Modernized Google Apps Script v3.3   ║
 * ║  Strict CSV Mapping | Auto-Webhook | Student ID Validation      ║
 * ╚══════════════════════════════════════════════════════════════════╝
 */

const CONFIG = {
  SECRET_KEY: PropertiesService.getScriptProperties().getProperty("SECRET_KEY") || "datalens2026",
  WEBHOOK_SECRET: PropertiesService.getScriptProperties().getProperty("WEBHOOK_SECRET") || "webhook-secret-key",
  DEPARTMENT_OPTIONS: [
    "School of Education & Humanities",
    "School of Engineering",
    "School of Engineering: Computer Science & Technology",
    "School of Engineering: Electronics and Communication",
    "School of Engineering: Mechanical Engineering",
    "School of Law",
    "School of Management & Commerce"
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

  // Section 1: Student Identity
  form.addSectionHeaderItem().setTitle("Step 1: Your Information");
  form.addTextItem().setTitle("Your Full Name").setRequired(true);
  form.addMultipleChoiceItem().setTitle("Department").setChoiceValues(CONFIG.DEPARTMENT_OPTIONS).setRequired(true);
  form.addTextItem().setTitle("Roll Number / Student ID").setRequired(true);

  // Section 2: Core Feedback
  form.addPageBreakItem().setTitle("Step 2: Session Value");
  form.addMultipleChoiceItem()
    .setTitle("Did the session help you gain a better understanding of industry trends or career paths?")
    .setChoiceValues(["Yes, significantly", "To some extent", "Not really"])
    .setRequired(true);
  
  form.addScaleItem()
    .setTitle("How would you rate the session overall? (1 – Poor | 5 – Excellent)")
    .setBounds(1, 5)
    .setLabels("1 ⭐", "5 ⭐")
    .setRequired(true);

  // Section 3: Detailed Feedback
  form.addPageBreakItem().setTitle("Step 3: Insights & Suggestions");
  form.addParagraphTextItem().setTitle("What aspect of the session did you find most valuable?").setRequired(true);
  form.addParagraphTextItem().setTitle("What improvements or suggestions would you recommend for future alumni sessions?").setRequired(false);
  form.addParagraphTextItem().setTitle("Any specific topics or areas you’d like future alumni speakers to cover?").setRequired(false);

  const formId = form.getId();
  
  // Store metadata
  PropertiesService.getScriptProperties().setProperty(`config_${formId}`, JSON.stringify({
    webhook_url: webhookUrl,
    event_id: eventId,
    speaker_name: speaker,
    venue_date: date
  }));

  // Setup Trigger
  ScriptApp.newTrigger('onFormSubmitTrigger').forForm(form).onFormSubmit().create();

  return _json(true, "Form created", { 
    form_id: formId, 
    form_url: form.getPublishedUrl() 
  }, 201);
}

// ─── TRIGGER LOGIC ───────────────────────────────────────────────────────────

function onFormSubmitTrigger(e) {
  try {
    const formId = e.source.getId();
    const props = PropertiesService.getScriptProperties();
    const config = JSON.parse(props.getProperty(`config_${formId}`) || "{}");
    
    if (!config.webhook_url) return;

    const answers = {};
    e.response.getItemResponses().forEach(ir => {
      const q = ir.getItem().getTitle();
      const a = ir.getResponse();
      
      // Mapping logic based on CSV matching
      if (q.includes("Full Name")) answers.name_of_student = a;
      else if (q.includes("Department")) answers.department_original = a;
      else if (q.includes("Roll Number")) answers.roll_no_original = a;
      else if (q.includes("industry trends")) answers.session_help_understanding = a;
      else if (q.includes("rate the session")) answers.session_rating = a;
      else if (q.includes("most valuable")) answers.aspect_most_valuable = a;
      else if (q.includes("improvements")) answers.improvements_suggestions = a;
      else if (q.includes("future alumni speakers to cover")) answers.future_topics = a;
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

    UrlFetchApp.fetch(config.webhook_url, {
      method: "post",
      contentType: "application/json",
      headers: { "Authorization": "Bearer " + CONFIG.WEBHOOK_SECRET },
      payload: JSON.stringify(payload),
      muteHttpExceptions: true
    });

  } catch (err) {
    console.error("Critical Webhook Error:", err.message);
  }
}

// ─── HELPERS ─────────────────────────────────────────────────────────────────

function _handleGetResponses(payload) {
  const formId = payload.form_id;
  try {
    const form = FormApp.openById(formId);
    const results = form.getResponses().map(resp => {
      const answers = { timestamp: resp.getTimestamp().toISOString() };
      resp.getItemResponses().forEach(ir => {
        const q = ir.getItem().getTitle();
        const a = ir.getResponse();
        if (q.includes("Full Name")) answers.name_of_student = a;
        else if (q.includes("Department")) answers.department_original = a;
        else if (q.includes("Roll Number")) answers.roll_no_original = a;
        else if (q.includes("industry trends")) answers.session_help_understanding = a;
        else if (q.includes("rate the session")) answers.session_rating = a;
        else if (q.includes("most valuable")) answers.aspect_most_valuable = a;
        else if (q.includes("improvements")) answers.improvements_suggestions = a;
        else if (q.includes("future alumni speakers to cover")) answers.future_topics = a;
      });
      return answers;
    });
    return _json(true, "Sync complete", results);
  } catch (e) { return _json(false, "Access error", e.message, 404); }
}

function _json(success, message, data, code = 200) {
  return ContentService.createTextOutput(JSON.stringify({ 
    success, message, data, timestamp: new Date().toISOString() 
  })).setMimeType(ContentService.MimeType.JSON);
}
