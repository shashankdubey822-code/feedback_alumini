-- ============================================================
-- certificate_trigger.sql
-- InsForge DB Trigger: Notify Edge Function on new certificate job
--
-- HOW TO DEPLOY:
-- 1. Open InsForge Dashboard → SQL Editor
-- 2. Paste this entire file and click Run
-- ============================================================

CREATE OR REPLACE FUNCTION notify_certificate_job()
RETURNS TRIGGER AS $$
BEGIN
  -- Fire when status is set to 'pending' (on insert or update)
  IF (TG_OP = 'INSERT' AND NEW.status = 'pending') OR 
     (TG_OP = 'UPDATE' AND NEW.status = 'pending' AND (OLD.status IS DISTINCT FROM 'pending' OR OLD.error_log IS NOT NULL)) THEN
    PERFORM realtime.publish(
      'certificate:pending',  -- channel name
      'new_job',              -- event name
      jsonb_build_object(
        'job_id',     NEW.id,
        'student_id', NEW.student_id,
        'event_id',   NEW.event_id,
        'created_at', NEW.created_at
      )
    );
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS on_certificate_job_insert ON certificate_jobs;

CREATE TRIGGER on_certificate_job_insert
  AFTER INSERT OR UPDATE ON certificate_jobs
  FOR EACH ROW
  EXECUTE FUNCTION notify_certificate_job();

SELECT 'certificate trigger created successfully' AS status;
