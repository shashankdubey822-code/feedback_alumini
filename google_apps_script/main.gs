/**
 * ╔══════════════════════════════════════════════════════════════════╗
 * ║   Alumni Feedback System — Advanced Google Apps Script v3.5     ║
 * ║  PRO-GRADE | 100% CSV SYNC | Error-Resilient | Self-Auth        ║
 * ╚══════════════════════════════════════════════════════════════════╝
 *
 * SCRIPT PROPERTIES (Project Settings → Script properties) — must match Hugging Face / backend:
 *   SECRET_KEY       — same as server env APPS_SCRIPT_SECRET (default datalens2026 if unset)
 *   WEBHOOK_SECRET   — same as server env WEBHOOK_SECRET (default webhook-secret-key if unset)
 *   WEBHOOK_URL      — optional; used only by hourly heartbeat (not per-form webhooks)
 *
 * SETUP: Deploy → New deployment → Web app → Execute as: Me → Who has access: Anyone (or your choice).
 * Run RUN_ME_TO_AUTHORIZE once after changes so Triggers + UrlFetch to your Space are allowed.
 * Windows "Run as administrator" does not affect this script; authorization is your Google account.
 */

const CONFIG = {
  SECRET_KEY: PropertiesService.getScriptProperties().getProperty("SECRET_KEY") || "datalens2026",
  WEBHOOK_SECRET: PropertiesService.getScriptProperties().getProperty("WEBHOOK_SECRET") || "webhook-secret-key",
  VERSION: "v3.5-Final-Sync",
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
    ScriptApp.newTrigger('onHeartbeatTrigger').timeBased().everyHours(1).create();
    Logger.log("✅ AUTHORIZATION SUCCESSFUL. Heartbeat established.");
  } catch (e) {
    Logger.log("⚠️ INFO: " + e.message);
    Logger.log("If asked for permissions, click REVIEW PERMISSIONS -> Select Account -> Advanced -> Allow.");
  }
}

/**
 * TRIGGER CLEANUP: 
 * Run this if you get the "Too many triggers" error!
 * It will delete all existing form triggers to make room for new ones.
 */
function CLEANUP_ALL_TRIGGERS() {
  Logger.log("Deleting all triggers to fix 'Too many triggers' error...");
  const triggers = ScriptApp.getProjectTriggers();
  triggers.forEach(t => ScriptApp.deleteTrigger(t));
  Logger.log("✅ All triggers deleted. You can now generate a new form.");
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
      case "close_form": return _handleCloseForm(payload);
      case "generate_certificate": return _handleGenerateCertificate(payload);
      case "diagnose": return _handleDiagnose(payload);
      case "ping": return _json(true, "Connectivity Active", { version: CONFIG.VERSION });
      default: return _json(false, "Unknown Action: " + action, null, 404);
    }
  } catch (err) {
    // Return the actual error in the 'data' field so backend can log it
    return _json(false, "Internal Execution Error", err.toString(), 500);
  }
}

// ─── ACTION HANDLERS ─────────────────────────────────────────────────────────

/**
 * Returns a full diagnostic report of the script's state
 */
function _handleDiagnose(payload) {
  const props = PropertiesService.getScriptProperties().getProperties();
  const triggers = ScriptApp.getProjectTriggers();
  
  const diagnosticData = {
    version: CONFIG.VERSION,
    properties_count: Object.keys(props).length,
    trigger_count: triggers.length,
    timezone: Session.getScriptTimeZone(),
    user_email: Session.getEffectiveUser().getEmail(),
    webhook_url_configured: !!props["WEBHOOK_URL"],
    auth_check: props["AUTH_CHECK"] || "Never verified"
  };
  
  return _json(true, "Diagnostic Data Retrieved", diagnosticData);
}

function _handleCreateForm(payload) {
  // ⚡ MANUAL RUN DETECTION
  if (!payload || typeof payload !== 'object') {
    Logger.log("⚠️ NOTICE: You clicked 'Run' in the editor. This only works from the Dashboard.");
    return _json(false, "Manual execution ignored.", null, 400);
  }

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

  // Step 1: Student Identity (Matches CSV Headers)
  form.addSectionHeaderItem().setTitle("Step 1: Your Information");
  form.addTextItem().setTitle("Name of Student").setRequired(true);
  
  if (payload.send_certificates) {
    const emailItem = form.addTextItem().setTitle("Email Address").setRequired(true);
    emailItem.setHelpText("Enter your correct email address to receive your certificate.");
    emailItem.setValidation(
      FormApp.createTextValidation()
        .requireTextIsEmail()
        .setHelpText("Must be a valid email address.")
        .build()
    );
  }
  form.addMultipleChoiceItem().setTitle("Department").setChoiceValues(CONFIG.DEPARTMENT_OPTIONS).setRequired(true);
  const rollItem = form.addTextItem().setTitle("Roll No.").setRequired(true);
  const rollPattern = "^2[Kk]\\d{2}[A-Za-z]{3,12}\\d{5}$";
  rollItem.setHelpText("Format: 2K + 2-digit batch year + programme code + 5 digits (e.g. 2K25EDUN01013, 2K24ECUN03021). No spaces.");
  rollItem.setValidation(
    FormApp.createTextValidation()
      .requireTextMatchesPattern(rollPattern)
      .setHelpText("Use your official roll number format, e.g. 2K25EDUN01013.")
      .build()
  );

  // Step 2: Session Value (Matches CSV Headers)
  form.addPageBreakItem().setTitle("Step 2: Session Value");
  form.addMultipleChoiceItem()
    .setTitle("Did the session help you gain a better understanding of industry trends or career paths?")
    .setChoiceValues(["Yes, significantly", "To some extent", "Not really"])
    .setRequired(true);
  
  form.addScaleItem()
    .setTitle("How would you rate the session overall?  \n(1 – Poor | 2 – Fair | 3 – Good | 4 – Very Good | 5 – Excellent)")
    .setBounds(1, 5)
    .setLabels("1 ⭐", "5 ⭐")
    .setRequired(true);

  // Step 3: Detailed Insights (Matches CSV Headers)
  form.addPageBreakItem().setTitle("Step 3: Insights & Suggestions");
  form.addParagraphTextItem().setTitle("What aspect of the session did you find most valuable?").setRequired(true);
  form.addParagraphTextItem().setTitle("What improvements or suggestions would you recommend for future alumni sessions?").setRequired(false);
  form.addParagraphTextItem().setTitle("Any specific topics or areas you’d like future alumni speakers to cover?").setRequired(false);

  const formId = form.getId();
  
  PropertiesService.getScriptProperties().setProperty(`config_${formId}`, JSON.stringify({
    webhook_url: webhookUrl,
    event_id: eventId,
    speaker_name: speaker,
    venue_date: date
  }));

  // ⚡ AUTOMATIC TRIGGER PRUNING (Personal accounts are limited to 20)
  const allTriggers = ScriptApp.getProjectTriggers();
  if (allTriggers.length > 15) {
    Logger.log("⚠️ Pruning old triggers to make room (Auto-Cleanup)...");
    for (let i = 0; i < 5; i++) {
       if (allTriggers[i]) try { ScriptApp.deleteTrigger(allTriggers[i]); } catch(f) {}
    }
  }

  // 1: Trigger for INSTANT webhooks on submission
  ScriptApp.newTrigger('onFormSubmitTrigger').forForm(form).onFormSubmit().create();

  // 2: Trigger for STRICT 24-hour closure
  const timeTrigger = ScriptApp.newTrigger('onAutoCloseFormTrigger').timeBased().after(24 * 60 * 60 * 1000).create();
  
  // Save mapping so the time trigger knows WHICH form to close
  PropertiesService.getScriptProperties().setProperty(`close_${timeTrigger.getUniqueId()}`, formId);

  console.log(`[SUCCESS] Form created for ${speaker} (ID: ${formId})`);
  return _json(true, "Form Generated Successfully", { 
    form_id: formId, 
    form_url: form.getPublishedUrl() 
  }, 201);
}

// ─── TRIGGER LOGIC ───────────────────────────────────────────────────────────

function onFormSubmitTrigger(e) {
  if (!e || !e.source) return;

  let formId = "";
  try {
    formId = e.source.getId();
    const config = JSON.parse(PropertiesService.getScriptProperties().getProperty(`config_${formId}`) || "{}");
    if (!config.webhook_url) return;

    const answers = {};
    e.response.getItemResponses().forEach(ir => {
      const q = ir.getItem().getTitle();
      const a = ir.getResponse();
      
      // Precision Header Mapping (Matches CSV perfectly)
      if (q.includes("Name of Student")) answers.name_of_student = a;
      else if (q.includes("Email Address")) answers.student_email = a;
      else if (q.includes("Department")) answers.department_original = a;
      else if (q.includes("Roll No.")) answers.roll_no_original = a;
      else if (q.includes("industry trends")) answers.session_help_understanding = a;
      else if (q.includes("rate the session")) answers.session_rating = a;
      else if (q.includes("most valuable")) answers.aspect_most_valuable = a;
      else if (q.includes("improvements")) answers.improvements_suggestions = a;
      else if (q.includes("future alumni speakers to cover")) answers.future_topics = a;
    });

    // Fallback if respondent email is collected natively
    try {
      const respEmail = e.response.getRespondentEmail();
      if (respEmail && !answers.student_email) {
        answers.student_email = respEmail;
      }
    } catch (err) {}

    const webhookPayload = JSON.stringify({
      form_id: formId,
      event_id: config.event_id,
      timestamp: new Date().toISOString(),
      responses: {
        ...answers,
        student_email: answers.student_email || "",
        alumni_speaker_name: config.speaker_name,
        date_of_lecture: config.venue_date
      }
    });

    const resp = UrlFetchApp.fetch(config.webhook_url, {
      method: "post",
      contentType: "application/json",
      headers: { "Authorization": "Bearer " + CONFIG.WEBHOOK_SECRET },
      payload: webhookPayload,
      muteHttpExceptions: true
    });

    const code = resp.getResponseCode();
    const text = resp.getContentText() || "";
    const preview = text.length > 500 ? text.substring(0, 500) + "…" : text;
    PropertiesService.getScriptProperties().setProperty(
      "LAST_WEBHOOK_SYNC",
      JSON.stringify({
        at: new Date().toISOString(),
        http_status: code,
        body_preview: preview,
        form_id: formId,
        webhook_host: (function () {
          try {
            return config.webhook_url.split("/")[2] || config.webhook_url;
          } catch (e) {
            return "";
          }
        })()
      })
    );

    if (code < 200 || code >= 300) {
      console.error("Webhook HTTP " + code + ": " + preview);
    } else {
      console.log("Webhook OK HTTP " + code + " for form " + formId);
    }

  } catch (err) {
    console.error("Advanced Webhook Failure:", err.toString());
    try {
      PropertiesService.getScriptProperties().setProperty(
        "LAST_WEBHOOK_SYNC",
        JSON.stringify({
          at: new Date().toISOString(),
          http_status: 0,
          error: err.toString(),
          form_id: formId || "unknown"
        })
      );
    } catch (ignore) {}
  }
}

function onAutoCloseFormTrigger(e) {
  // This runs exactly 24 hours after creation
  if (!e || !e.triggerUid) return;
  
  const triggerId = e.triggerUid;
  const formId = PropertiesService.getScriptProperties().getProperty(`close_${triggerId}`);
  
  if (formId) {
    try {
      const form = FormApp.openById(formId);
      form.setAcceptingResponses(false);
      form.setCustomClosedFormMessage("Sorry this form is closed, reach your mentor");
      PropertiesService.getScriptProperties().deleteProperty(`close_${triggerId}`);
    } catch(err) {
      console.error("Failed to auto-close form:", err);
    }
  }
  
  // Cleanup the used trigger
  const triggers = ScriptApp.getProjectTriggers();
  for (let i = 0; i < triggers.length; i++) {
    if (triggers[i].getUniqueId() === triggerId) {
      ScriptApp.deleteTrigger(triggers[i]);
      break;
    }
  }
}

// ─── DATA RETRIEVAL & CLOSURE ────────────────────────────────────────────────

function _handleGetResponses(payload) {
  // ⚡ MANUAL RUN DETECTION
  if (!payload || typeof payload !== 'object' || !payload.form_id) {
    Logger.log("⚠️ NOTICE: You clicked 'Run' in the editor. This only works from the Dashboard.");
    return _json(false, "Manual execution ignored.", null, 400);
  }

  const formId = payload.form_id;
  try {
    const form = FormApp.openById(formId);
    if (!form) throw new Error("Could not access Form.");
    
    const results = form.getResponses().map(resp => {
      const answers = { timestamp: resp.getTimestamp().toISOString() };
      resp.getItemResponses().forEach(ir => {
        const q = ir.getItem().getTitle();
        const a = ir.getResponse();
        
        if (q.indexOf("Name of Student") > -1) answers.name_of_student = a;
        else if (q.indexOf("Department") > -1) answers.department_original = a;
        else if (q.indexOf("Roll No.") > -1) answers.roll_no_original = a;
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

function _handleCloseForm(payload) {
  if (!payload || typeof payload !== 'object' || !payload.form_id) {
    return _json(false, "Missing form_id in payload.", null, 400);
  }
  
  const formId = payload.form_id;
  try {
    const form = FormApp.openById(formId);
    if (!form) throw new Error("Could not access Form.");
    
    // STRICT CLOSURE
    form.setAcceptingResponses(false);
    form.setCustomClosedFormMessage("Sorry this form is closed, reach your mentor");
    
    return _json(true, "Form Strictly Closed on Google Servers", { form_id: formId });
  } catch (e) {
    return _json(false, "Closure Failure", e.toString(), 500);
  }
}

// ─── JSON HELPER ─────────────────────────────────────────────────────────────

function _json(success, message, data, code = 200) {
  const output = { success, message, data, v: CONFIG.VERSION, timestamp: new Date().toISOString() };
  return ContentService.createTextOutput(JSON.stringify(output)).setMimeType(ContentService.MimeType.JSON);
}

/**
 * Sends a periodic heartbeat to the backend to verify connectivity
 */
function onHeartbeatTrigger() {
  const props = PropertiesService.getScriptProperties();
  const webhookUrl = props.getProperty("WEBHOOK_URL");
  const secret = props.getProperty("WEBHOOK_SECRET") || "webhook-secret-key";
  
  if (!webhookUrl) {
    Logger.log("Heartbeat skipped: WEBHOOK_URL not set.");
    return;
  }
  
  try {
    const payload = {
      action: "heartbeat",
      timestamp: new Date().toISOString(),
      form_id: "HEARTBEAT"
    };
    
    UrlFetchApp.fetch(webhookUrl, {
      method: "post",
      contentType: "application/json",
      headers: { "Authorization": "Bearer " + secret },
      payload: JSON.stringify(payload),
      muteHttpExceptions: true
    });
    Logger.log("Heartbeat sent to: " + webhookUrl);
  } catch (e) {
    Logger.log("Heartbeat failed: " + e.toString());
  }
}

/**
 * ONE-TIME SETUP (Project Settings script properties are read-only when you have 50+ properties):
 * 1. Set the SAME WEBHOOK_SECRET in Hugging Face Space → Secrets.
 * 2. In the Apps Script editor, select this function → Run → allow permissions.
 * 3. Check Executions / Logs for "Saved WEBHOOK_SECRET and SECRET_KEY".
 * 4. Submit a test form; LAST_WEBHOOK_SYNC should show http_status 200, not 401.
 * 5. Remove the literal strings below (or delete this whole function) after success — do not leave secrets in source long-term.
 */
function ONE_TIME_SET_SECRETS() {
  const p = PropertiesService.getScriptProperties();
  p.setProperty("WEBHOOK_SECRET", "DL_wh_9fK2mPq7vNx4Rt8sLw3");
  p.setProperty("SECRET_KEY", "datalens2026");
  Logger.log("Saved WEBHOOK_SECRET and SECRET_KEY (must match HF WEBHOOK_SECRET and APPS_SCRIPT_SECRET).");
}

function _handleGenerateCertificate(payload) {
  if (!payload || typeof payload !== 'object') {
    return _json(false, "Data Error: Payload is required.", null, 400);
  }

  const templateId = payload.template_id;
  const studentName = payload.student_name;
  const studentEmail = payload.student_email;
  const rollNo = payload.roll_no || "";
  const department = payload.department || "";
  const speakerName = payload.speaker_name || "";
  const venueDate = payload.venue_date || "";

  if (!templateId) return _json(false, "Data Error: template_id is required.", null, 400);
  if (!studentName) return _json(false, "Data Error: student_name is required.", null, 400);
  if (!studentEmail) return _json(false, "Data Error: student_email is required.", null, 400);

  try {
    // 1. Copy the Google Slides template
    const templateFile = DriveApp.getFileById(templateId);
    const copyName = `Certificate - ${studentName} - ${rollNo}`;
    const copyFile = templateFile.makeCopy(copyName);
    const copyId = copyFile.getId();

    // 2. Open the copy and replace placeholders
    const presentation = SlidesApp.openById(copyId);
    const slides = presentation.getSlides();
    
    slides.forEach(slide => {
      slide.getShapes().forEach(shape => {
        if (shape.hasText()) {
          const textRange = shape.getText();
          // Case-insensitive/flexible placeholder replacement
          textRange.replaceAllText("{{name}}", studentName);
          textRange.replaceAllText("{{Name}}", studentName);
          textRange.replaceAllText("{{roll}}", rollNo);
          textRange.replaceAllText("{{Roll}}", rollNo);
          textRange.replaceAllText("{{roll_no}}", rollNo);
          textRange.replaceAllText("{{RollNo}}", rollNo);
          textRange.replaceAllText("{{dept}}", department);
          textRange.replaceAllText("{{Dept}}", department);
          textRange.replaceAllText("{{department}}", department);
          textRange.replaceAllText("{{speaker}}", speakerName);
          textRange.replaceAllText("{{Speaker}}", speakerName);
          textRange.replaceAllText("{{date}}", venueDate);
          textRange.replaceAllText("{{Date}}", venueDate);
        }
      });
    });

    // Save and close presentation to persist modifications
    presentation.saveAndClose();

    // 3. Export as PDF
    const pdfBlob = copyFile.getAs('application/pdf');

    // 4. Send Email
    const emailSubject = `Certificate of Attendance: Guest Lecture by ${speakerName}`;
    const emailBody = `Dear ${studentName},\n\n` +
                      `Thank you for attending the guest lecture by ${speakerName} on ${venueDate}.\n\n` +
                      `Please find attached your Certificate of Attendance.\n\n` +
                      `Best regards,\n` +
                      `Department Team`;
                      
    MailApp.sendEmail({
      to: studentEmail,
      subject: emailSubject,
      body: emailBody,
      attachments: [pdfBlob]
    });

    // 5. Clean up the copied Google Slides file to save Drive space
    try {
      copyFile.setTrashed(true);
    } catch(cleanupErr) {
      console.warn("Failed to trash temporary file copy: " + cleanupErr);
    }

    return _json(true, "Certificate generated and sent successfully", {
      student_name: studentName,
      student_email: studentEmail
    });

  } catch (err) {
    return _json(false, "Certificate Generation Failure", err.toString(), 500);
  }
}
