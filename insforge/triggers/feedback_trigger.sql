-- ============================================================
-- feedback_trigger.sql
-- InsForge DB Trigger: Notify Edge Function on new feedback
--
-- HOW TO DEPLOY:
-- 1. Open InsForge Dashboard → SQL Editor
-- 2. Paste this entire file and click Run
-- 3. The trigger will be active immediately
-- ============================================================

-- Function called by the trigger
CREATE OR REPLACE FUNCTION notify_new_feedback()
RETURNS TRIGGER AS $$
BEGIN
  -- Fire on insert, or on update if the feedback text fields actually changed
  IF TG_OP = 'INSERT' OR 
     (TG_OP = 'UPDATE' AND (
        COALESCE(NEW.aspect_most_valuable, '') != COALESCE(OLD.aspect_most_valuable, '') OR
        COALESCE(NEW.improvements_suggestions, '') != COALESCE(OLD.improvements_suggestions, '') OR
        COALESCE(NEW.future_topics, '') != COALESCE(OLD.future_topics, '') OR
        COALESCE(NEW.session_rating, 0) != COALESCE(OLD.session_rating, 0)
     )) THEN
    PERFORM realtime.publish(
      'feedback:new',   -- channel name
      LOWER(TG_OP),     -- event name: 'insert' or 'update'
      jsonb_build_object(
        'response_id',              NEW.id,
        'event_id',                 NEW.event_id,
        'student_id',               NEW.student_id,
        'aspect_most_valuable',     NEW.aspect_most_valuable,
        'improvements_suggestions', NEW.improvements_suggestions,
        'future_topics',            NEW.future_topics,
        'session_rating',           NEW.session_rating,
        'submitted_at',             NEW.submitted_at
      )
    );
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Drop existing trigger if it exists
DROP TRIGGER IF EXISTS on_feedback_insert ON feedback_responses;

-- Create trigger on INSERT OR UPDATE
CREATE TRIGGER on_feedback_insert
  AFTER INSERT OR UPDATE ON feedback_responses
  FOR EACH ROW
  EXECUTE FUNCTION notify_new_feedback();

-- Verify
SELECT 'feedback trigger created successfully' AS status;
