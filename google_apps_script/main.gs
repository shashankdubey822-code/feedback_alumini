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
    "School of Education",
    "CSD",
    "ME",
    "R and AI",
    "EC",
    "School of Law",
    "School of Business",
    "School of Science"
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
      case "verify_template": return _handleVerifyTemplate(payload);
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
  try {
    form.setCollectEmail(false);
  } catch (e) {
    Logger.log("setCollectEmail not supported: " + e.toString());
  }

  try {
    form.setRequireLogin(false); // Allow anyone (including personal Gmails) to access the form
  } catch (e) {
    Logger.log("setRequireLogin not supported: " + e.toString());
  }

  try {
    form.setAllowResponseEdits(false);
  } catch (e) {
    Logger.log("setAllowResponseEdits not supported: " + e.toString());
  }

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
  try {
    ScriptApp.newTrigger('onFormSubmitTrigger').forForm(form).onFormSubmit().create();
  } catch (e) {
    Logger.log("⚠️ Failed to create form submit trigger: " + e.toString());
  }

  // 2: Trigger for STRICT 24-hour closure
  try {
    const timeTrigger = ScriptApp.newTrigger('onAutoCloseFormTrigger').timeBased().after(24 * 60 * 60 * 1000).create();
    // Save mapping so the time trigger knows WHICH form to close
    PropertiesService.getScriptProperties().setProperty(`close_${timeTrigger.getUniqueId()}`, formId);
  } catch (e) {
    Logger.log("⚠️ Failed to create auto-close time trigger: " + e.toString());
  }

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
    try {
      form.setCustomClosedFormMessage("Sorry this form is closed, reach your mentor");
    } catch (msgErr) {
      console.warn("Could not set custom closed message: " + msgErr.toString());
    }
    
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
  p.setProperty("SENDER_EMAIL", "shashankdubey822@gmail.com"); // Restored back to MRU email due to slide permissions
  Logger.log("Saved WEBHOOK_SECRET, SECRET_KEY, and SENDER_EMAIL.");
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
  const deptShort = {
    "School of Education": "SOEH",
    "School of Education and Humanities": "SOEH",
    "CSD": "CSD",
    "ME": "ME",
    "R and AI": "R & AI",
    "EC": "ECE",
    "School of Law": "SoL",
    "School of Business": "SoB",
    "School of Science": "SoS"
  };
  const shortDept = deptShort[department] || department;
  const speakerName = payload.speaker_name || "";
  const venueDate = payload.venue_date || "";
  const lectureTitle = payload.lecture_title || "";

  if (!templateId) return _json(false, "Data Error: template_id is required.", null, 400);
  if (!studentName) return _json(false, "Data Error: student_name is required.", null, 400);
  if (!studentEmail) return _json(false, "Data Error: student_email is required.", null, 400);

  let targetTemplateId = templateId;
  if (templateId === "PREDEFINED") {
    const departmentTemplates = {
      "School of Education": PropertiesService.getScriptProperties().getProperty("TEMPLATE_EDU") || "",
      "CSD": PropertiesService.getScriptProperties().getProperty("TEMPLATE_CSD") || "",
      "ME": PropertiesService.getScriptProperties().getProperty("TEMPLATE_ME") || "",
      "R and AI": PropertiesService.getScriptProperties().getProperty("TEMPLATE_RAI") || "",
      "EC": PropertiesService.getScriptProperties().getProperty("TEMPLATE_EC") || "",
      "School of Law": PropertiesService.getScriptProperties().getProperty("TEMPLATE_LAW") || "",
      "School of Business": PropertiesService.getScriptProperties().getProperty("TEMPLATE_BUS") || "",
      "School of Science": PropertiesService.getScriptProperties().getProperty("TEMPLATE_SCI") || ""
    };
    targetTemplateId = departmentTemplates[department] || "";
    if (!targetTemplateId) {
      return _json(false, "No predefined template configured for department: " + department, null, 400);
    }
  }

  try {
    // 1. Copy the Google Slides template
    const templateFile = DriveApp.getFileById(targetTemplateId);
    const copyName = `Certificate - ${studentName} - ${rollNo}`;
    const copyFile = templateFile.makeCopy(copyName);
    const copyId = copyFile.getId();

    // 2. Open the copy and replace placeholders
    const presentation = SlidesApp.openById(copyId);
    const slides = presentation.getSlides();
    
    slides.forEach(slide => {
      slide.getShapes().forEach(shape => {
        const textRange = shape.getText();
        if (textRange) {
          // Snapshots paragraph alignment
          const alignments = [];
          textRange.getParagraphs().forEach(p => {
            alignments.push(p.getParagraphStyle().getParagraphAlignment());
          });
          
          // Case-insensitive/flexible placeholder replacement
          textRange.replaceAllText("«StudentName»", studentName);
          textRange.replaceAllText("{{StudentName}}", studentName);
          textRange.replaceAllText("{{name}}", studentName);
          textRange.replaceAllText("{{Name}}", studentName);
          textRange.replaceAllText("{{roll}}", rollNo);
          textRange.replaceAllText("{{Roll}}", rollNo);
          textRange.replaceAllText("{{roll_no}}", rollNo);
          textRange.replaceAllText("{{RollNo}}", rollNo);
          
          const titleValue = lectureTitle || "";
          textRange.replaceAllText("«LectureTitle»", titleValue);
          textRange.replaceAllText("{{lecture}}", titleValue);
          textRange.replaceAllText("{{LectureTitle}}", titleValue);
          textRange.replaceAllText("{{lecture_title}}", titleValue);
          if (!titleValue) {
            textRange.replaceAllText("\u201c{{LectureTitle}}\u201d,", "");
            textRange.replaceAllText("\u201c{{lecture_title}}\u201d,", "");
            textRange.replaceAllText("\u201c{{lecture}}\u201d,", "");
            textRange.replaceAllText("\"\",", "");
            textRange.replaceAllText("\u201c\u201d,", "");
          }
          
          textRange.replaceAllText("«AlumniName»", speakerName);
          textRange.replaceAllText("{{AlumniName}}", speakerName);
          textRange.replaceAllText("{{speaker}}", speakerName);
          textRange.replaceAllText("{{Speaker}}", speakerName);
          
          textRange.replaceAllText("«Date»", venueDate);
          textRange.replaceAllText("{{date}}", venueDate);
          textRange.replaceAllText("{{Date}}", venueDate);
          
          textRange.replaceAllText("«Department»", department);
          textRange.replaceAllText("{{Department}}", department);
          textRange.replaceAllText("{{dept}}", department);
          textRange.replaceAllText("{{Dept}}", department);
          textRange.replaceAllText("{{department}}", department);
          
          textRange.replaceAllText("«ProgramName»", shortDept);
          textRange.replaceAllText("{{ProgramName}}", shortDept);
          textRange.replaceAllText("{{program}}", shortDept);
          textRange.replaceAllText("{{Program}}", shortDept);
          
          textRange.replaceAllText("«Semester»", "");
          textRange.replaceAllText("{{Semester}}", "");
          textRange.replaceAllText("{{semester}}", "");

          // ── Restore Alignment ─────────────────────────────────────────────────
          // replaceAllText() can reset paragraph alignment to LEFT.
          // Re-apply the snapshotted alignment to each paragraph.
          try {
            const parasAfter = textRange.getParagraphs();
            parasAfter.forEach((para, i) => {
              try {
                const savedAlign = alignments[i] || SlidesApp.ParagraphAlignment.CENTER;
                para.getRange().getParagraphStyle().setParagraphAlignment(savedAlign);
              } catch(e) {}
            });
          } catch(e) {}
        }

        // ── Auto-Shrink: reduce font size if text is too long for the shape ────
        try {
          const shapeW = shape.getWidth();
          const shapeH = shape.getHeight();
          if (shapeW > 0 && shapeH > 0) {
            const tr2 = shape.getText();
            const fullText2 = tr2 ? tr2.asString().trim() : '';
            if (fullText2) {
              let curFs = 12;
              try {
                const r0 = tr2.getParagraphs()[0].getRichText().getRuns();
                if (r0 && r0.length > 0) {
                  const fs0 = r0[0].getTextStyle().getFontSize();
                  if (fs0 && fs0 > 0) curFs = fs0;
                }
              } catch(e) {}

              const MIN_FS = 7;
              let fs = curFs;
              let fits = false;
              while (!fits && fs > MIN_FS) {
                const cpl  = Math.max(1, Math.floor(shapeW / (fs * 0.55)));
                const lfIt = Math.max(1, Math.floor(shapeH / (fs * 1.35)));
                let need = 0;
                fullText2.split('\n').forEach(ln => {
                  need += Math.max(1, Math.ceil(ln.length / cpl));
                });
                if (need <= lfIt) { fits = true; } else { fs -= 1; }
              }
              if (fs < curFs) {
                try {
                  tr2.getParagraphs().forEach(p => {
                    p.getRichText().getRuns().forEach(r => {
                      r.getTextStyle().setFontSize(fs);
                    });
                  });
                } catch(e) {}
              }
            }
          }
        } catch(shrinkErr) {}
      });
    });

    // ── Overflow / Layout Check ──────────────────────────────────────────────
    // Google Slides API has no native isOverflowing() method.
    // We use a heuristic: estimate text lines needed vs lines that fit in the shape.
    // Formula: charsPerLine ≈ shapeWidthPts / (fontSize * 0.55)  [monospace estimate]
    //          linesNeeded  ≈ totalChars / charsPerLine
    //          linesFit     ≈ shapeHeightPts / (fontSize * 1.35)  [line-height factor]
    const overflowWarnings = [];
    try {
      const filledSlides = presentation.getSlides();
      filledSlides.forEach((slide, slideIdx) => {
        slide.getShapes().forEach(shape => {
          try {
            const tr = shape.getText();
            if (!tr) return;
            const fullText = tr.asString().trim();
            if (!fullText) return;

            // Get shape physical size in points (1 pt = 1/72 inch)
            const shapeW = shape.getWidth();   // points
            const shapeH = shape.getHeight();  // points
            if (!shapeW || !shapeH || shapeW <= 0 || shapeH <= 0) return;

            // Estimate font size from first paragraph's first text run
            let fontSize = 12; // default fallback
            try {
              const paras = tr.getParagraphs();
              if (paras && paras.length > 0) {
                const runs = paras[0].getRichText().getRuns();
                if (runs && runs.length > 0) {
                  const fs = runs[0].getTextStyle().getFontSize();
                  if (fs && fs > 0) fontSize = fs;
                }
              }
            } catch (fsErr) { /* use default */ }

            // Heuristic calculations
            const avgCharWidthPts  = fontSize * 0.55;  // average char width
            const lineHeightPts    = fontSize * 1.35;  // line height with spacing
            const charsPerLine     = Math.max(1, Math.floor(shapeW / avgCharWidthPts));
            const linesFit         = Math.max(1, Math.floor(shapeH / lineHeightPts));

            // Count actual lines (split on newlines first, then wrap estimate)
            const hardLines = fullText.split("\n");
            let estimatedLinesNeeded = 0;
            hardLines.forEach(line => {
              estimatedLinesNeeded += Math.max(1, Math.ceil(line.length / charsPerLine));
            });

            // Flag if estimated lines exceed capacity by >20% (buffer for heuristic error)
            if (estimatedLinesNeeded > linesFit * 1.2) {
              // Identify which field is in this shape
              const lowerText = fullText.toLowerCase();
              let fieldHint = "unknown field";
              if (lowerText.includes(studentName.toLowerCase())) fieldHint = "Student Name";
              else if (lowerText.includes(speakerName.toLowerCase())) fieldHint = "Speaker Name";
              else if (lectureTitle && lowerText.includes(lectureTitle.toLowerCase())) fieldHint = "Lecture Title";
              else if (lowerText.includes(venueDate.toLowerCase())) fieldHint = "Venue Date";

              overflowWarnings.push({
                slide: slideIdx + 1,
                field: fieldHint,
                shape_width_pts: Math.round(shapeW),
                shape_height_pts: Math.round(shapeH),
                font_size: fontSize,
                chars_per_line: charsPerLine,
                lines_fit: linesFit,
                lines_estimated: estimatedLinesNeeded,
                text_preview: fullText.substring(0, 60) + (fullText.length > 60 ? "..." : "")
              });
            }
          } catch (shapeErr) { /* skip broken shape */ }
        });
      });
    } catch (overflowCheckErr) {
      console.warn("Overflow check failed: " + overflowCheckErr);
    }

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
                      
    const senderEmail = PropertiesService.getScriptProperties().getProperty("SENDER_EMAIL") || "";
    const mailOptions = {
      attachments: [pdfBlob]
    };
    if (senderEmail) {
      mailOptions.from = senderEmail;
    }

    GmailApp.sendEmail(studentEmail, emailSubject, emailBody, mailOptions);

    // 5. Clean up the copied Google Slides file to save Drive space
    try {
      copyFile.setTrashed(true);
    } catch(cleanupErr) {
      console.warn("Failed to trash temporary file copy: " + cleanupErr);
    }

    const hasWarnings = overflowWarnings.length > 0;
    return _json(true, hasWarnings ? "success_with_warnings" : "Certificate generated and sent successfully", {
      student_name: studentName,
      student_email: studentEmail,
      overflow_warnings: overflowWarnings  // empty array = no issues
    });

  } catch (err) {
    return _json(false, "Certificate Generation Failure", err.toString(), 500);
  }
}

function _handleVerifyTemplate(payload) {
  if (!payload || typeof payload !== 'object' || !payload.template_id) {
    return _json(false, "Missing template_id in payload.", null, 400);
  }
  const templateId = payload.template_id;
  if (templateId === "PREDEFINED") {
    return _json(true, "Predefined templates bypassed.", null, 200);
  }
  try {
    DriveApp.getFileById(templateId);
    return _json(true, "Template is valid and accessible.", null, 200);
  } catch (err) {
    return _json(false, "Template not found or permission denied.", err.toString(), 400);
  }
}

function SETUP_PREDEFINED_TEMPLATES() {
  const p = PropertiesService.getScriptProperties();
  p.setProperty("TEMPLATE_EDU", "1UQE5K_PdrZo7ZaDhTPFcyRao2PKgCP7F9nR0byWI5nI");
  p.setProperty("TEMPLATE_CSD", "1oda7oUQSFm0wk6fDXbN5GdaM1faLbGul1wbBevWb-9Y");
  p.setProperty("TEMPLATE_ME",  "1l4T1JiMhn2PY6hYC4Xy4DSUslzyz834XCxZ02WgB1qQ");
  p.setProperty("TEMPLATE_RAI", "1vpT9yBsycuE9Jk3ieE8025zXW6P9E6cXDM3eG19q0pQ");
  p.setProperty("TEMPLATE_EC",  "1iwZYerDqWeh6F7NaKALLV9jeMCc4qVr3DFFiDM0H03U");
  p.setProperty("TEMPLATE_LAW", "1i4NPQpQEuzlJ2x7R5aa_Ce_wepNKIB7HKdUtbJlDhnw");
  p.setProperty("TEMPLATE_BUS", "1XrVO-Om4CukE8Jlp2Vpz9dGKRZnvJvqR4NutHDCATHw");
  p.setProperty("TEMPLATE_SCI", "1xlTishh5Mj5jJhwY-Lq4fWxCKrGKcvZ55Ug1oqYzL0k");
  Logger.log("Predefined template settings updated.");
}

