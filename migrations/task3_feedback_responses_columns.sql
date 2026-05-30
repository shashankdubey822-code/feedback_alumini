ALTER TABLE feedback_responses
  ADD COLUMN IF NOT EXISTS extracted_date DATE,
  ADD COLUMN IF NOT EXISTS extracted_time TIME,
  ADD COLUMN IF NOT EXISTS session_technical_clarity INTEGER,
  ADD COLUMN IF NOT EXISTS form_source VARCHAR(50) DEFAULT 'google_form',
  ADD COLUMN IF NOT EXISTS record_status VARCHAR(20) DEFAULT 'active';
