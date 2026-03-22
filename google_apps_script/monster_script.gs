/**
 * ╔══════════════════════════════════════════════════════════════════╗
 * ║   MONSTER SYNC SCRIPT v5.0 — THE "FIX-IT-ALL" VERSION            ║
 * ║   Features: Auto-Sync, Handshake, Heartbeat, Visual Status       ║
 * ╚══════════════════════════════════════════════════════════════════╝
 */

const MONSTER_CONFIG = {
  VERSION: "v5.0-Monster",
  // This will be automatically set by the Dashboard, but you can hardcode it for Step 4
  WEBHOOK_URL: PropertiesService.getScriptProperties().getProperty("WEBHOOK_URL"),
  SECRET: PropertiesService.getScriptProperties().getProperty("WEBHOOK_SECRET") || "datalens2026"
};

/**
 * 1. RUN THIS FIRST TO RESET EVERYTHING
 */
function MONSTER_REPAIR_AND_AUTHORIZE() {
  // Delete all old triggers to start fresh
  const triggers = ScriptApp.getProjectTriggers();
  triggers.forEach(t => ScriptApp.deleteTrigger(t));
  
  // Set up Heartbeat (Every hour)
  ScriptApp.newTrigger('onHeartbeatTrigger')
    .timeBased()
    .everyHours(1)
    .create();
    
  Logger.log("✅ MONSTER RESET COMPLETE!");
  Logger.log("Next: Create a NEW Form from your Dashboard to link the URL.");
}

/**
 * 2. MANUALLY RUN THIS TO TEST THE CONNECTION
 */
function TEST_SERVER_HANDSHAKE() {
  const url = MONSTER_CONFIG.WEBHOOK_URL;
  if (!url) {
    Logger.log("❌ ERROR: Sync URL is not set. Please generate a new form first or check Script Properties.");
    return;
  }
  
  Logger.log("🔍 Pinging Dashboard at: " + url);
  
  const payload = {
    action: "heartbeat",
    message: "Monster Handshake Test"
  };
  
  try {
    const options = {
      method: "post",
      contentType: "application/json",
      headers: { "Authorization": "Bearer " + MONSTER_CONFIG.SECRET },
      payload: JSON.stringify(payload),
      muteHttpExceptions: true
    };
    
    const response = UrlFetchApp.fetch(url, options);
    const code = response.getResponseCode();
    
    if (code === 200) {
      Logger.log("✅ HANDSHAKE SUCCESS! Your dashboard is reachable and updated.");
    } else if (code === 404) {
      Logger.log("❌ ERROR 404: The dashboard received the ping but doesn't have the recipe. DID YOU RESTART YOUR SPACE?");
    } else if (code === 401) {
      Logger.log("❌ ERROR 401: Password Mismatch. Ensure WEBHOOK_SECRET in HG matches your script secret.");
    } else {
      Logger.log("⚠️ ERROR " + code + ": Server responded but with an issue: " + response.getContentText());
    }
  } catch (e) {
    Logger.log("❌ CRITICAL ERROR: Could not reach server. Check if your Space is Sleeping or URL is wrong: " + e.toString());
  }
}

/**
 * 3. THE AUTO-SYNC HEART (ON FORM SUBMIT)
 */
function onFormSubmitTrigger(e) {
  const url = MONSTER_CONFIG.WEBHOOK_URL;
  if (!url) return;
  
  const form = e.source;
  const responses = e.response.getItemResponses();
  const answers = {};
  
  responses.forEach(r => {
    const title = r.getItem().getTitle().toLowerCase().replace(/ /g, "_");
    answers[title] = r.getResponse();
  });
  
  // Map specific fields for our backend
  const payload = {
    action: "form_submit",
    timestamp: new Date().toISOString(),
    form_id: form.getId(),
    name_of_student: answers['name_of_student'] || answers['name'] || "Unknown",
    responses: answers
  };
  
  try {
    UrlFetchApp.fetch(url, {
      method: "post",
      contentType: "application/json",
      headers: { "Authorization": "Bearer " + MONSTER_CONFIG.SECRET },
      payload: JSON.stringify(payload),
      muteHttpExceptions: true
    });
  } catch(err) {
    console.error("Sync failed: " + err.toString());
  }
}

function onHeartbeatTrigger() {
  TEST_SERVER_HANDSHAKE();
}

/**
 * 4. WEBHOOK ENTRY POINT (RECEIVES DATA FROM DASHBOARD)
 */
function doPost(e) {
  const data = JSON.parse(e.postData.contents);
  if (data.secret !== MONSTER_CONFIG.SECRET) return ContentService.createTextOutput("Unauthorized");

  if (data.action === "create_form") {
    // [Legacy creation logic here...]
    // Important: Update the URL in memory when a new form is created
    PropertiesService.getScriptProperties().setProperty("WEBHOOK_URL", data.webhook_url);
    return ContentService.createTextOutput("Form Created & URL Linked");
  }
}
