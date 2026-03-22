# 👹 MONSTER SYNC - ULTIMATE SETUP GUIDE

This is a foolproof setup to get your Auto-Sync and Dashboard Pop-ups working 100%.

## 🚨 STEP 0: THE MOST IMPORTANT PART
You MUST **Restart your Hugging Face Space** right now. 
- Even if you added the variables in the UI, the backend cannot "see" them until you click **"Restart this Space"** in your Settings.
- My diagnostic tool shows your server is currently running "Old Code" from 22 hours ago. 

---

## 🛠 STEP 1: HUGGING FACE SETTINGS
Make sure you have THESE 2 variables in your Space **Settings** -> **Variables and Secrets**:
1. `PUBLIC_URL` = `https://vrfefavr-feedback-dashboard.hf.space` (or your actual Space URL)
2. `WEBHOOK_SECRET` = `datalens2026`

---

## 🛠 STEP 2: UPDATE GOOGLE SCRIPT
1. Open your **Google Apps Script** editor.
2. DELETE everything inside it.
3. PASTE the contents of `google_apps_script/monster_script.gs` (found in this project).
4. Click **Save** (💾).

---

## 🛠 STEP 3: ACTIVATE THE MONSTER
1. In the Script Editor, select the function **`MONSTER_REPAIR_AND_AUTHORIZE`** from the dropdown menu and click **Run**.
   - This cleans up all old broken links and sets up a new Heartbeat.
2. Now, select **`TEST_SERVER_HANDSHAKE`** and click **Run**.
3. **Check the Execution Log** at the bottom:
   - If it says `✅ HANDSHAKE SUCCESS!`, you are officially connected! 
   - If it says `404`, it means you forgot to **Restart your Space** (Step 0).

---

## 🛠 STEP 4: LINK THE URL
Go to your Dashboard and **Generate a NEW Google Form**. 
- This "pushes" your public URL into Google's memory.
- After this, every form submission will trigger a pop-up on your dashboard!

---

## 📊 DASHBOARD STATUS
I have added a **"Sync Status"** indicator at the bottom of your Dashboard sidebar.
- **Sync Active** (Green Dot) = Everything is perfect.
- **URL Not Set** (Red Dot) = You missed Step 1.
- **Server Offline** = Your Space is sleeping or restarting.
