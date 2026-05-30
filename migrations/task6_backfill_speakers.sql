INSERT INTO speakers (name)
SELECT DISTINCT speaker_name FROM events
WHERE speaker_name IS NOT NULL AND speaker_name <> ''
ON CONFLICT (name) DO NOTHING;

UPDATE events e
SET speaker_id = s.id
FROM speakers s
WHERE e.speaker_name = s.name;
