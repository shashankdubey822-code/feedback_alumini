CREATE TABLE IF NOT EXISTS speakers (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name VARCHAR(255) UNIQUE NOT NULL,
  department VARCHAR(255),
  bio TEXT,
  linkedin_url VARCHAR(500),
  created_at TIMESTAMPTZ DEFAULT now()
);
ALTER TABLE events ADD COLUMN IF NOT EXISTS speaker_id UUID REFERENCES speakers(id);
