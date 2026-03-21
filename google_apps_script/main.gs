/**
 * ╔══════════════════════════════════════════════════════════════════╗
 * ║   Alumni Feedback System — Advanced Google Apps Script v3.4     ║
 * ║  PRO-GRADE | Exact CSV Mapping | Error-Resilient | Self-Auth    ║
 * ╚══════════════════════════════════════════════════════════════════╝
 */

const CONFIG = {
  SECRET_KEY: PropertiesService.getScriptProperties().getProperty("SECRET_KEY") || "datalens2026",
  WEBHOOK_SECRET: PropertiesService.getScriptProperties().getProperty("WEBHOOK_SECRET") || "webhook-secret-key",
  VERSION: "v3.4-Advanced",
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

/**
 * MANUAL PERMISSION REPAIR:
 * If you get "Server Error", run this function once manually in the editor!
 */
function RUN_ME_TO_AUTHORIZE() {
  Logger.log("Permission Check: Verifying Forms, Properties, and Triggers...");
  try {
    const props = PropertiesService.getScriptProperties();
    props.setProperty("AUTH_CHECK", new Date().toISOString());
    FormApp.getActiveForm(); // Triggers Form permission
    ScriptApp.getProjectTriggers(); // Triggers ScriptApp permission
    Logger.log("✅ AUTHORIZATION SUCCESSFUL. You can now use the dashboard.");
  } catch (e) {
    Logger.log("⚠️ INFO: " + e.message);
    Logger.log("If asked for permissions, click REVIEW PERMISSIONS -> Select Account -> Advanced -> Allow.");
  }
}

// ─── ENTRY POINTS ────────────────────────────────────────────────────────────

function doPost(e) {
  try {
    if (!e || !e.postData || !e.postData.contents) {
      return _json(false, "Invalid Request: No payload received.", null, 400);
    }
    
    const payload = JSON.parse(e.postData.contents);
    if (!payload || payload.secret !== CONFIG.SECRET_KEY) {
      return _json(false, "Unauthorized Access: Secret key mismatch.", null, 401);
    }

    const action = (payload.action || "").toLowerCase();
    switch (action) {
      case "create_form": return _handleCreateForm(payload);
      case "get_responses": return _handleGetResponses(payload);
      case "ping": return _json(true, "Connectivity Active", { version: CONFIG.VERSION });
      default: return _json(false, "Unknown Action: " + action, null, 404);
    }
  } catch (err) {
    return _json(false, "Internal Execution Error", err.toString(), 500);
  }
}

// ─── ACTION HANDLERS ─────────────────────────────────────────────────────────

function _handleCreateForm(payload) {
  const speaker = payload.speaker_name;
  const date = payload.venue_date;
  const eventId = payload.event_id;
  const webhookUrl = payload.webhook_url;

  if (!speaker || !date) return _json(false, "Data Error: Speaker and date are required.", null, 400);

  // Exact matches for CSV synchronization
  const form = FormApp.create(`Student Feedback: ${speaker}`);
  form.setDescription(`Session: ${date} | Speaker: ${speaker}\nJoin us in providing feedback for continuous improvement.`);
  form.setCollectEmail(false);
  form.setAllowResponseEdits(false);

  // Step 1: Student Identity
  form.addSectionHeaderItem().setTitle("Step 1: Your Information");
  form.addTextItem().setTitle("Your Full Name").setRequired(true);
  form.addMultipleChoiceItem().setTitle("Department").setChoiceValues(CONFIG.DEPARTMENT_OPTIONS).setRequired(true);
  form.addTextItem().setTitle("Roll Number / Student ID").setRequired(true);

  // Step 2: Session Value (EXACT CSV MAPPING)
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

  // Step 3: Detailed Insights
  form.addPageBreakItem().setTitle("Step 3: Insights & Suggestions");
  form.addParagraphTextItem().setTitle("What aspect of the session did you find most valuable?").setRequired(true);
  form.addParagraphTextItem().setTitle("What improvements or suggestions would you recommend for future alumni sessions?").setRequired(false);
  form.addParagraphTextItem().setTitle("Any specific topics or areas you’d like future alumni speakers to cover?").setRequired(false);

  const formId = form.getId();
  
  // Storage for submission correlation
  PropertiesService.getScriptProperties().setProperty(`config_${formId}`, JSON.stringify({
    webhook_url: webhookUrl,
    event_id: eventId,
    speaker_name: speaker,
    venue_date: date
  }));

  // Automatic Trigger Attachment
  ScriptApp.newTrigger('onFormSubmitTrigger').forForm(form).onFormSubmit().create();

  return _json(true, "Form Generated Successfully", { 
    form_id: formId, 
    form_url: form.getPublishedUrl() 
  }, 201);
}

// ─── TRIGGER LOGIC ───────────────────────────────────────────────────────────

function onFormSubmitTrigger(e) {
  if (!e || !e.source) {
    console.warn("Trigger warning: Expected event object missing (this happens if run manually).");
    return;
  }
  
  try {
    const formId = e.source.getId();
    const config = JSON.parse(PropertiesService.getScriptProperties().getProperty(`config_${formId}`) || "{}");
    
    if (!config.webhook_url) return;

    const answers = {};
    e.response.getItemResponses().forEach(ir => {
      const q = ir.getItem().getTitle();
      const a = ir.getResponse();
      
      // Precision Header Mapping (Matches CSV perfectly)
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
    console.error("Advanced Webhook Failure:", err.toString());
  }
}

// ─── DATA RETRIEVAL ──────────────────────────────────────────────────────────

function _handleGetResponses(payload) {
  const formId = payload.form_id;
  try {
    const form = FormApp.openById(formId);
    if (!form) throw new Error("Could not access Form. Ensure script is owner.");
    
    const results = form.getResponses().map(resp => {
      const answers = { timestamp: resp.getTimestamp().toISOString() };
      resp.getItemResponses().forEach(ir => {
        const q = ir.getItem().getTitle();
        const a = ir.getResponse();
        
        if (q.indexOf("Full Name") > -1) answers.name_of_student = a;
        else if (q.indexOf("Department") > -1) answers.department_original = a;
        else if (q.indexOf("Roll Number") > -1) answers.roll_no_original = a;
        else if (q.indexOf("industry trends") > -1) answers.session_help_understanding = a;
        else if (q.indexOf("rate the session") > -1) answers.session_rating = a;
        else if (q.indexOf("most valuable") > -1) answers.aspect_most_valuable = a;
        else if (q.indexOf("improvements") > -1) answers.improvements_suggestions = a;
        else if (q.indexOf("future alumni speakers to cover") > -1) answers.future_topics = a;
      });
      return answers;
    });
    return _json(true, "Responses Extracted", results);
  } catch (e) {
    return _json(false, "Extraction Failure", e.toString(), 404);
  }
}

// ─── JSON HELPER ─────────────────────────────────────────────────────────────

function _json(success, message, data, code = 200) {
  const output = { 
    success: success, 
    message: message, 
    data: data, 
    v: CONFIG.VERSION,
    timestamp: new Date().toISOString() 
  };
  return ContentService.createTextOutput(JSON.stringify(output)).setMimeType(ContentService.MimeType.JSON);
}
