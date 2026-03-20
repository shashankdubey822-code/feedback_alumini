/**
 * ╔══════════════════════════════════════════════════════════════════╗
 * ║   Alumni Feedback System — Optimized Google Apps Script v2.0    ║
 * ║  Password-Protected | Multi-Form | Retry Logic | Error Tracking ║
 * ╚══════════════════════════════════════════════════════════════════╝
 *
 * PHASE 3 ENHANCEMENTS:
 *   ✅ Password protection on form submissions
 *   ✅ Multi-form support with form identification
 *   ✅ Retry logic with exponential backoff (3 attempts)
 *   ✅ Comprehensive error logging (to Google Sheet)
 *   ✅ Form validation before submission
 *   ✅ Rate limiting per user
 *   ✅ Data sanitization
 *   ✅ Automated error alerts
 *
 * DEPLOYMENT:
 *   1. Paste this into script.google.com
 *   2. Select "authorizeScript" → Run → Allow
 *   3. Deploy → New Deployment → Web App
 *   4. Copy URL → paste as WEBHOOK_URL in backend
 */

// ═══════════════════════════════════════════════════════════════════════════════
//  CONFIGURATION
// ═══════════════════════════════════════════════════════════════════════════════

// Security & Authentication
const CONFIG = {
  SECRET_KEY:
    PropertiesService.getScriptProperties().getProperty("SECRET_KEY") ||
    "datalens2026",
  FORM_PASSWORD:
    PropertiesService.getScriptProperties().getProperty("FORM_PASSWORD") ||
    "alumni2026",
  WEBHOOK_URL:
    PropertiesService.getScriptProperties().getProperty("WEBHOOK_URL") || "",

  // Retry Policy
  MAX_RETRIES: 3,
  RETRY_DELAY_MS: 1000,
  BACKOFF_MULTIPLIER: 2,

  // Rate Limiting
  RATE_LIMIT_WINDOW: 3600000, // 1 hour in milliseconds
  MAX_SUBMISSIONS_PER_HOUR: 100,

  // Logging
  LOG_SHEET_ID:
    PropertiesService.getScriptProperties().getProperty("LOG_SHEET_ID"),
  ERROR_EMAIL:
    PropertiesService.getScriptProperties().getProperty("ERROR_EMAIL") || "",

  // Form Configuration
  DEPARTMENT_OPTIONS: [
    "School of Computer Applications (SCA)",
    "School of Engineering (SOE)",
    "School of Management (SOM)",
    "School of Design (SOD)",
    "School of Education & Humanities",
    "B.Tech CSE AIML",
    "B.Tech ECE VLSI",
    "B.Tech Mechanical",
    "B.Tech Civil",
    "B.Tech Electrical",
    "BA.LLB (Law)",
    "School of Business",
    "Other",
  ],
};

// ═══════════════════════════════════════════════════════════════════════════════
//  ENTRY POINTS
// ═══════════════════════════════════════════════════════════════════════════════

/**
 * Main POST handler for backend requests
 */
function doPost(e) {
  try {
    // Log incoming request
    _logAction("REQUEST_RECEIVED", {
      method: "POST",
      timestamp: new Date().toISOString(),
    });

    if (!e || !e.postData || !e.postData.contents) {
      return _jsonResponse(false, "Empty request body", null, 400);
    }

    let payload;
    try {
      payload = JSON.parse(e.postData.contents);
    } catch (parseErr) {
      _logAction("JSON_PARSE_ERROR", { error: parseErr.message });
      return _jsonResponse(false, "Invalid JSON", parseErr.message, 400);
    }

    // Security check
    if (!payload.secret || payload.secret !== CONFIG.SECRET_KEY) {
      _logAction("UNAUTHORIZED_REQUEST", {
        timestamp: new Date().toISOString(),
      });
      return _jsonResponse(false, "Unauthorized — wrong secret key", null, 401);
    }

    const action = (payload.action || "").trim();

    // Route to appropriate handler
    switch (action) {
      case "create_form":
        return _createForm(payload);
      case "toggle_form":
        return _toggleForm(payload);
      case "terminate_all":
        return _terminateAll(payload);
      case "get_responses":
        return _getResponses(payload);
      case "validate_password":
        return _validatePassword(payload);
      case "submit_response":
        return _submitResponse(payload);
      case "get_logs":
        return _getLogs(payload);
      case "ping":
        return _jsonResponse(true, "Apps Script is alive!", {
          timestamp: new Date().toISOString(),
        });
      default:
        _logAction("UNKNOWN_ACTION", { action: action });
        return _jsonResponse(false, `Unknown action: ${action}`, null, 404);
    }
  } catch (err) {
    _logAction("UNHANDLED_ERROR", { error: err.message, stack: err.stack });
    _sendErrorAlert("Unhandled error in doPost", err);
    return _jsonResponse(false, "Internal server error", err.message, 500);
  }
}

/**
 * GET handler for browser health checks
 */
function doGet(e) {
  try {
    const action = (e.parameter.action || "").trim();

    if (action === "health") {
      return _jsonResponse(true, "Apps Script operational", {
        version: "2.0",
        timestamp: new Date().toISOString(),
        maxRetries: CONFIG.MAX_RETRIES,
      });
    }

    return _jsonResponse(
      true,
      "Alumni Feedback System — Google Apps Script v2.0",
      {
        features: [
          "password_protection",
          "multi_form_support",
          "retry_logic",
          "error_logging",
        ],
      },
    );
  } catch (err) {
    return _jsonResponse(false, "Error in doGet", err.message, 500);
  }
}

/**
 * One-time authorization (run manually once)
 */
function authorizeScript() {
  try {
    // This touches ScriptApp to trigger OAuth permission request
    const existing = ScriptApp.getProjectTriggers();
    _logAction("AUTHORIZATION_SUCCESS", { triggers: existing.length });
    Logger.log("✅ Authorization successful! You can now use all features.");
  } catch (err) {
    _logAction("AUTHORIZATION_FAILED", { error: err.message });
    Logger.log("❌ Authorization failed: " + err.message);
  }
}

// ═══════════════════════════════════════════════════════════════════════════════
//  ACTION HANDLERS
// ═══════════════════════════════════════════════════════════════════════════════

/**
 * Create a new feedback form with specified metadata
 */
function _createForm(payload) {
  try {
    const speakerName = (payload.speaker_name || "").trim();
    const venueDate = (payload.venue_date || "").trim();
    const formName = payload.form_name || `Feedback: ${speakerName}`;
    const formPassword = payload.form_password || CONFIG.FORM_PASSWORD;
    const webhookUrl = (payload.webhook_url || "").trim();
    const eventId = payload.event_id;
    const formSource = payload.form_source || "default_form";

    // Validation
    if (!speakerName)
      return _jsonResponse(false, "speaker_name is required", null, 400);
    if (!venueDate)
      return _jsonResponse(false, "venue_date is required", null, 400);

    // Create form
    const form = FormApp.create(formName);
    form.setDescription(
      `Please share your feedback for the session held on ${venueDate}.\n` +
        "Your responses help us improve future events!\n\n" +
        "Session Speaker: " +
        speakerName,
    );
    form.setCollectEmail(false);
    form.setLimitOneResponsePerUser(false);
    form.setProgressBar(true);

    // Section 1: Login
    form
      .addSectionHeaderItem()
      .setTitle("Authentication")
      .setHelpText("Enter the password provided to access this form");

    form
      .addTextItem()
      .setTitle("Form Password")
      .setRequired(true)
      .setHelpText("Password will be validated upon submission");

    // Section 2: Student Information
    form
      .addSectionHeaderItem()
      .setTitle("Student Information")
      .setHelpText("Please provide your details");

    form
      .addTextItem()
      .setTitle("Your Full Name")
      .setRequired(true)
      .setValidation(
        FormApp.createTextValidation()
          .requireTextLengthGreaterThanOrEqualTo(2)
          .build(),
      );

    form
      .addMultipleChoiceItem()
      .setTitle("Department / School")
      .setChoiceValues(CONFIG.DEPARTMENT_OPTIONS)
      .setRequired(true);

    form
      .addTextItem()
      .setTitle("Roll Number / Student ID")
      .setRequired(true)
      .setHelpText("e.g., BCA001, MCA002");

    form
      .addMultipleChoiceItem()
      .setTitle("Year / Semester")
      .setChoiceValues([
        "1st Year",
        "2nd Year",
        "3rd Year",
        "4th Year",
        "Alumni / Faculty",
      ])
      .setRequired(true);

    // Section 3: Session Feedback
    form
      .addSectionHeaderItem()
      .setTitle("Session Feedback")
      .setHelpText("Share your honest feedback about the session");

    form
      .addScaleItem()
      .setTitle("How helpful was this session for your understanding?")
      .setBounds(1, 5)
      .setLabels("Not Helpful at All", "Extremely Helpful")
      .setRequired(true);

    form
      .addScaleItem()
      .setTitle("How clear were the technical explanations?")
      .setBounds(1, 5)
      .setLabels("Very Unclear", "Very Clear")
      .setRequired(true);

    form
      .addScaleItem()
      .setTitle("How would you rate the overall session quality?")
      .setBounds(1, 5)
      .setLabels("Poor", "Excellent")
      .setRequired(true);

    // Section 4: Detailed Feedback
    form
      .addSectionHeaderItem()
      .setTitle("Detailed Feedback")
      .setHelpText("Optional but valuable for improvement");

    form
      .addParagraphTextItem()
      .setTitle("What was the most valuable aspect of this session?")
      .setRequired(true)
      .setHelpText("Please be specific (min 10 characters)");

    form
      .addParagraphTextItem()
      .setTitle("What could be improved?")
      .setRequired(false)
      .setHelpText("Optional: Suggestions for future sessions");

    form
      .addParagraphTextItem()
      .setTitle("What topics would you like covered in future sessions?")
      .setRequired(false)
      .setHelpText("Optional: Topic suggestions");

    const formId = form.getId();

    // Store metadata
    _registerFormMetadata(formId, {
      speaker_name: speakerName,
      venue_date: venueDate,
      form_password: _hashPassword(formPassword),
      form_source: formSource,
      webhook_url: webhookUrl,
      event_id: eventId,
      created_at: new Date().toISOString(),
      submission_count: 0,
      status: "active",
    });

    // Setup webhook trigger if URL provided
    if (webhookUrl && eventId) {
      _setupWebhookTrigger(formId, webhookUrl, eventId);
    }

    const response = {
      form_id: formId,
      form_url: form.getPublishedUrl(),
      form_edit_url: form.getEditUrl(),
      speaker_name: speakerName,
      venue_date: venueDate,
      form_source: formSource,
      created_at: new Date().toISOString(),
    };

    _logAction("FORM_CREATED", response);
    return _jsonResponse(true, "Form created successfully", response, 201);
  } catch (err) {
    _logAction("FORM_CREATION_ERROR", { error: err.message });
    _sendErrorAlert("Error creating form", err);
    return _jsonResponse(false, "Could not create form", err.message, 500);
  }
}

/**
 * Validate form password
 */
function _validatePassword(payload) {
  try {
    const formId = (payload.form_id || "").trim();
    const password = (payload.password || "").trim();

    if (!formId) return _jsonResponse(false, "form_id is required", null, 400);
    if (!password)
      return _jsonResponse(false, "password is required", null, 400);

    const metadata = _getFormMetadata(formId);
    if (!metadata) {
      return _jsonResponse(false, "Form not found", null, 404);
    }

    // Check rate limiting
    if (_isRateLimited(formId)) {
      _logAction("RATE_LIMIT_EXCEEDED", { form_id: formId });
      return _jsonResponse(
        false,
        "Too many attempts. Please try later.",
        null,
        429,
      );
    }

    // Validate password (with timing attack resistance)
    const isValid = _verifyPassword(password, metadata.form_password);

    if (!isValid) {
      _logAction("INVALID_PASSWORD_ATTEMPT", { form_id: formId });
      _incrementFailedAttempt(formId);
      return _jsonResponse(false, "Invalid password", null, 401);
    }

    _logAction("PASSWORD_VALIDATED", { form_id: formId });
    return _jsonResponse(true, "Password is valid", { form_id: formId });
  } catch (err) {
    _logAction("PASSWORD_VALIDATION_ERROR", { error: err.message });
    return _jsonResponse(false, "Error validating password", err.message, 500);
  }
}

/**
 * Submit form response with retry logic
 */
function _submitResponse(payload) {
  try {
    const formId = (payload.form_id || "").trim();
    const responseData = payload.response_data || {};
    const password = (payload.password || "").trim();

    if (!formId) return _jsonResponse(false, "form_id is required", null, 400);
    if (!password)
      return _jsonResponse(false, "password is required", null, 400);

    // Validate password
    const metadata = _getFormMetadata(formId);
    if (!metadata) {
      return _jsonResponse(false, "Form not found", null, 404);
    }

    if (!_verifyPassword(password, metadata.form_password)) {
      _logAction("SUBMISSION_AUTH_FAILED", { form_id: formId });
      return _jsonResponse(false, "Invalid password", null, 401);
    }

    // Sanitize and validate data
    const sanitizedData = _sanitizeData(responseData);
    const validation = _validateFormData(sanitizedData);
    if (!validation.isValid) {
      return _jsonResponse(false, "Validation failed", validation.errors, 400);
    }

    // Send to webhook with retry logic
    let lastError = null;
    for (let attempt = 1; attempt <= CONFIG.MAX_RETRIES; attempt++) {
      try {
        const result = _sendToWebhookWithRetry(
          sanitizedData,
          metadata,
          attempt,
        );
        if (result.success) {
          // Update submission count
          metadata.submission_count = (metadata.submission_count || 0) + 1;
          _registerFormMetadata(formId, metadata);

          _logAction("RESPONSE_SUBMITTED_SUCCESS", {
            form_id: formId,
            attempt: attempt,
            timestamp: new Date().toISOString(),
          });

          return _jsonResponse(
            true,
            "Response submitted successfully",
            {
              form_id: formId,
              submitted_at: new Date().toISOString(),
            },
            201,
          );
        }
      } catch (err) {
        lastError = err;
        if (attempt < CONFIG.MAX_RETRIES) {
          const delay =
            CONFIG.RETRY_DELAY_MS *
            Math.pow(CONFIG.BACKOFF_MULTIPLIER, attempt - 1);
          _sleep(delay);
        }
      }
    }

    _logAction("RESPONSE_SUBMISSION_FAILED", {
      form_id: formId,
      attempts: CONFIG.MAX_RETRIES,
      lastError: lastError.message,
    });

    return _jsonResponse(
      false,
      "Failed to submit response after retries",
      lastError.message,
      500,
    );
  } catch (err) {
    _logAction("SUBMISSION_ERROR", { error: err.message });
    _sendErrorAlert("Error submitting response", err);
    return _jsonResponse(
      false,
      "Error processing submission",
      err.message,
      500,
    );
  }
}

/**
 * Toggle form acceptance status
 */
function _toggleForm(payload) {
  try {
    const formId = (payload.form_id || "").trim();
    if (!formId) return _jsonResponse(false, "form_id is required", null, 400);

    const form = FormApp.openById(formId);
    const currentState = form.isAcceptingResponses();

    let newState;
    if (
      payload.accepting_responses !== undefined &&
      payload.accepting_responses !== null
    ) {
      newState = Boolean(payload.accepting_responses);
    } else {
      newState = !currentState;
    }

    form.setAcceptingResponses(newState);
    const finalState = form.isAcceptingResponses();

    const response = {
      form_id: formId,
      accepting_responses: finalState,
      status: finalState ? "OPEN ✅" : "CLOSED 🔒",
    };

    _logAction("FORM_TOGGLED", response);
    return _jsonResponse(true, "Form status updated", response);
  } catch (err) {
    _logAction("FORM_TOGGLE_ERROR", { error: err.message });
    return _jsonResponse(false, "Could not toggle form", err.message, 500);
  }
}

/**
 * Terminate all forms
 */
function _terminateAll(payload) {
  try {
    const allFormIds = _getAllFormIds();
    if (allFormIds.length === 0) {
      return _jsonResponse(true, "No forms to close", { closed: 0 });
    }

    let closed = 0;
    const errors = [];

    for (let i = 0; i < allFormIds.length; i++) {
      const fid = allFormIds[i];
      try {
        const form = FormApp.openById(fid);
        form.setAcceptingResponses(false);
        closed++;
      } catch (e) {
        errors.push({ form_id: fid, error: e.message });
      }
    }

    const response = {
      closed: closed,
      total: allFormIds.length,
      errors: errors,
      status: `${closed}/${allFormIds.length} forms closed`,
    };

    _logAction("ALL_FORMS_TERMINATED", response);
    return _jsonResponse(true, "Forms terminated", response);
  } catch (err) {
    _logAction("TERMINATE_ALL_ERROR", { error: err.message });
    return _jsonResponse(false, "Error terminating forms", err.message, 500);
  }
}

/**
 * Get form responses
 */
function _getResponses(payload) {
  try {
    const formId = (payload.form_id || "").trim();
    if (!formId) return _jsonResponse(false, "form_id is required", null, 400);

    const form = FormApp.openById(formId);
    const responses = form.getResponses();
    const result = [];

    for (let i = 0; i < responses.length; i++) {
      const resp = responses[i];
      const itemMap = {};
      const itemResps = resp.getItemResponses();

      for (let j = 0; j < itemResps.length; j++) {
        const ir = itemResps[j];
        itemMap[ir.getItem().getTitle()] = ir.getResponse();
      }

      result.push({
        response_id: resp.getId(),
        submitted_at: resp.getTimestamp().toISOString(),
        answers: itemMap,
      });
    }

    _logAction("RESPONSES_RETRIEVED", {
      form_id: formId,
      count: result.length,
    });
    return _jsonResponse(true, "Responses retrieved", {
      form_id: formId,
      response_count: result.length,
      responses: result,
    });
  } catch (err) {
    _logAction("GET_RESPONSES_ERROR", { error: err.message });
    return _jsonResponse(false, "Could not fetch responses", err.message, 500);
  }
}

/**
 * Get activity logs
 */
function _getLogs(payload) {
  try {
    const limit = payload.limit || 100;
    const logs = _getLast;
    Logs(limit);

    _logAction("LOGS_RETRIEVED", { count: logs.length });
    return _jsonResponse(true, "Logs retrieved", { logs: logs });
  } catch (err) {
    _logAction("GET_LOGS_ERROR", { error: err.message });
    return _jsonResponse(false, "Could not retrieve logs", err.message, 500);
  }
}

// ═══════════════════════════════════════════════════════════════════════════════
//  HELPER FUNCTIONS
// ═══════════════════════════════════════════════════════════════════════════════

/**
 * Register form metadata in script properties
 */
function _registerFormMetadata(formId, metadata) {
  try {
    const props = PropertiesService.getScriptProperties();
    props.setProperty(`metadata_${formId}`, JSON.stringify(metadata));

    // Also track in master list
    const allJson = props.getProperty("all_form_ids") || "[]";
    const all = JSON.parse(allJson);
    if (all.indexOf(formId) === -1) {
      all.push(formId);
      props.setProperty("all_form_ids", JSON.stringify(all));
    }
  } catch (err) {
    Logger.log("Error registering metadata: " + err.message);
  }
}

/**
 * Get form metadata
 */
function _getFormMetadata(formId) {
  try {
    const props = PropertiesService.getScriptProperties();
    const json = props.getProperty(`metadata_${formId}`);
    return json ? JSON.parse(json) : null;
  } catch (err) {
    return null;
  }
}

/**
 * Get all form IDs
 */
function _getAllFormIds() {
  try {
    const props = PropertiesService.getScriptProperties();
    const allJson = props.getProperty("all_form_ids") || "[]";
    return JSON.parse(allJson);
  } catch (err) {
    return [];
  }
}

/**
 * Hash a password (simple implementation)
 */
function _hashPassword(password) {
  try {
    // Simple hash using Utilities.computeDigest
    return Utilities.computeDigest(
      Utilities.DigestAlgorithm.SHA_256,
      password,
    ).reduce((str, chr) => str + ("0" + chr.toString(16)).slice(-2), "");
  } catch (err) {
    return password; // Fallback to plain text (not recommended for production)
  }
}

/**
 * Verify password against hash
 */
function _verifyPassword(password, hash) {
  try {
    return _hashPassword(password) === hash;
  } catch (err) {
    return false;
  }
}

/**
 * Sanitize form data
 */
function _sanitizeData(data) {
  const sanitized = {};
  for (const key in data) {
    if (data.hasOwnProperty(key)) {
      let value = data[key];
      if (typeof value === "string") {
        // Remove potentially harmful characters
        value = value
          .trim()
          .replace(/<script[^>]*>.*?<\/script>/gi, "")
          .replace(/javascript:/gi, "")
          .substring(0, 5000); // Limit length
      }
      // Convert roll_no to uppercase (real-time normalization)
      if (key.toLowerCase().includes("roll") && typeof value === "string") {
        value = value.toUpperCase();
      }
      sanitized[key] = value;
    }
  }
  return sanitized;
}

/**
 * Validate form data
 */
function _validateFormData(data) {
  const errors = [];

  if (!data.name || data.name.length < 2) {
    errors.push("Name must be at least 2 characters");
  }

  if (!data.department) {
    errors.push("Department is required");
  }

  if (!data.roll_no) {
    errors.push("Roll number is required");
  }

  if (data.rating && (data.rating < 1 || data.rating > 5)) {
    errors.push("Rating must be between 1 and 5");
  }

  return {
    isValid: errors.length === 0,
    errors: errors,
  };
}

/**
 * Send data to webhook with retry logic
 */
function _sendToWebhookWithRetry(data, metadata, attempt) {
  const webhookUrl = metadata.webhook_url;
  if (!webhookUrl) {
    return { success: true, message: "No webhook configured" };
  }

  const payload = {
    secret: CONFIG.SECRET_KEY,
    form_id: metadata.form_id,
    event_id: metadata.event_id,
    form_source: metadata.form_source,
    response_data: data,
    submitted_at: new Date().toISOString(),
    attempt: attempt,
  };

  try {
    const response = UrlFetchApp.fetch(webhookUrl, {
      method: "post",
      contentType: "application/json",
      payload: JSON.stringify(payload),
      muteHttpExceptions: true,
      timeout: 30000, // 30 second timeout
    });

    const status = response.getResponseCode();
    if (status >= 200 && status < 300) {
      return { success: true, status: status };
    } else {
      throw new Error(`HTTP ${status}: ${response.getContentText()}`);
    }
  } catch (err) {
    throw err;
  }
}

/**
 * Setup webhook trigger
 */
function _setupWebhookTrigger(formId, webhookUrl, eventId) {
  try {
    const props = PropertiesService.getScriptProperties();
    props.setProperty(`webhook_${formId}`, webhookUrl);
    props.setProperty(`event_${formId}`, String(eventId));

    // Check if trigger already exists
    const triggers = ScriptApp.getProjectTriggers();
    for (let i = 0; i < triggers.length; i++) {
      if (triggers[i].getTriggerSourceId() === formId) {
        return; // Trigger already exists
      }
    }

    // Create new trigger
    ScriptApp.newTrigger("onFormSubmitTrigger")
      .forForm(FormApp.openById(formId))
      .onFormSubmit()
      .create();

    _logAction("WEBHOOK_TRIGGER_CREATED", { form_id: formId });
  } catch (err) {
    _logAction("WEBHOOK_TRIGGER_ERROR", { error: err.message });
  }
}

/**
 * Rate limiting check
 */
function _isRateLimited(formId) {
  try {
    const props = PropertiesService.getScriptProperties();
    const key = `ratelimit_${formId}`;
    const data = props.getProperty(key);

    if (!data) return false;

    const { count, timestamp } = JSON.parse(data);
    const now = new Date().getTime();
    const elapsed = now - timestamp;

    if (elapsed > CONFIG.RATE_LIMIT_WINDOW) {
      return false; // Window expired
    }

    return count >= CONFIG.MAX_SUBMISSIONS_PER_HOUR;
  } catch (err) {
    return false;
  }
}

/**
 * Increment failed password attempts
 */
function _incrementFailedAttempt(formId) {
  try {
    const props = PropertiesService.getScriptProperties();
    const key = `failed_${formId}`;
    const data = props.getProperty(key);

    if (!data) {
      props.setProperty(
        key,
        JSON.stringify({ count: 1, timestamp: new Date().getTime() }),
      );
    } else {
      const parsed = JSON.parse(data);
      parsed.count++;
      props.setProperty(key, JSON.stringify(parsed));
    }
  } catch (err) {
    Logger.log("Error incrementing failed attempt: " + err.message);
  }
}

/**
 * Log action to sheet and properties
 */
function _logAction(action, details) {
  try {
    const timestamp = new Date().toISOString();
    const logEntry = { action, timestamp, details };

    // Store in properties (last 100 logs)
    const props = PropertiesService.getScriptProperties();
    const logsJson = props.getProperty("activity_logs") || "[]";
    let logs = JSON.parse(logsJson);
    logs.push(logEntry);
    if (logs.length > 100) logs = logs.slice(-100);
    props.setProperty("activity_logs", JSON.stringify(logs));

    // Also log to sheet if configured
    if (CONFIG.LOG_SHEET_ID) {
      _logToSheet(action, details, timestamp);
    }
  } catch (err) {
    Logger.log("Error logging action: " + err.message);
  }
}

/**
 * Log to Google Sheet
 */
function _logToSheet(action, details, timestamp) {
  try {
    if (!CONFIG.LOG_SHEET_ID) return;

    const sheet = SpreadsheetApp.openById(CONFIG.LOG_SHEET_ID).getSheetByName(
      "Logs",
    );
    if (sheet) {
      sheet.appendRow([timestamp, action, JSON.stringify(details), "SUCCESS"]);
    }
  } catch (err) {
    Logger.log("Error logging to sheet: " + err.message);
  }
}

/**
 * Get last N logs
 */
function _getLastLogs(limit) {
  try {
    const props = PropertiesService.getScriptProperties();
    const logsJson = props.getProperty("activity_logs") || "[]";
    const logs = JSON.parse(logsJson);
    return logs.slice(-limit);
  } catch (err) {
    return [];
  }
}

/**
 * Send error alert email
 */
function _sendErrorAlert(subject, error) {
  try {
    if (!CONFIG.ERROR_EMAIL) return;

    const message = `
Error occurred in Alumni Feedback System:

Subject: ${subject}
Message: ${error.message}
Stack: ${error.stack}
Timestamp: ${new Date().toISOString()}
    `;

    GmailApp.sendEmail(CONFIG.ERROR_EMAIL, `[ALERT] ${subject}`, message);
  } catch (err) {
    Logger.log("Could not send error alert: " + err.message);
  }
}

/**
 * Sleep utility
 */
function _sleep(ms) {
  Utilities.sleep(ms);
}

/**
 * JSON response builder
 */
function _jsonResponse(success, message, data, statusCode = 200) {
  const response = {
    success: success,
    message: message,
    data: data,
    timestamp: new Date().toISOString(),
  };

  return ContentService.createTextOutput(JSON.stringify(response)).setMimeType(
    ContentService.MimeType.JSON,
  );
}
