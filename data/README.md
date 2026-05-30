# Data Directory Structure

This folder contains persistent data for the Alumni Feedback System on Hugging Face Spaces.

## Subfolders

- **`uploads/`** — Uploaded CSV files from users
- **`backups/`** — Database and data backups
- **`exports/`** — Exported reports and analytics data

## Important for HF Spaces

This directory persists across deployments when properly configured in your HF Space settings:
1. Go to your HF Space Settings
2. Under "Persistent Storage", set the path to `/tmp/data` (or according to HF configuration)
3. Each subfolder will retain its contents between rebuilds

## How Data is Used

- **uploads/**: Stores CSV files uploaded through the web interface
- **backups/**: Automatic backups of the SQLite database (backed up via API)
- **exports/**: Generated JSON exports, reports, and analytics snapshots

---

*Last updated: 2026-03-20*
