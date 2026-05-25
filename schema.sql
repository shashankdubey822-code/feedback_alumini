-- ==========================================
-- DATALENS SUPABASE DATABASE SCHEMA SETUP
-- Copy and paste this script into your Supabase SQL Editor and click RUN.
-- ==========================================

-- 1. Enable the pgvector extension for Vector Semantic RAG
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. Create the Events table
CREATE TABLE IF NOT EXISTS events (
    id BIGSERIAL PRIMARY KEY,
    speaker_name TEXT NOT NULL,
    venue_date DATE NOT NULL,
    form_id TEXT,
    form_url TEXT,
    form_edit_url TEXT,
    status TEXT DEFAULT 'ACTIVE',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- 3. Create the Student Feedback Data table
CREATE TABLE IF NOT EXISTS dashboard_data (
    id BIGSERIAL PRIMARY KEY,
    timestamp_original TEXT,
    timestamp_normalized TEXT,
    name_of_student TEXT,
    name_normalized TEXT,
    department_original TEXT,
    department_cleaned TEXT,
    roll_no_original TEXT,
    roll_no_cleaned TEXT,
    date_of_lecture DATE,
    alumni_speaker_name TEXT,
    session_help_understanding TEXT,
    session_rating INTEGER,
    session_technical_clarity INTEGER,
    aspect_most_valuable TEXT,
    improvements_suggestions TEXT,
    future_topics TEXT,
    form_source TEXT,
    data_quality_score REAL,
    is_duplicate_flag INTEGER DEFAULT 0,
    record_status TEXT DEFAULT 'VALID',
    cleaned_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    dl_sentiment_score REAL,
    dl_sentiment_label TEXT,
    dl_keywords JSONB, -- Stores categorizations, individual sentiments, and keywords
    dl_processed INTEGER DEFAULT 0,
    embedding vector(384) -- 384-dimensional vector from all-MiniLM-L6-v2 embedding model
);

-- 4. Create index for fast retrieval of unprocessed rows
CREATE INDEX IF NOT EXISTS idx_dl_processed ON dashboard_data(dl_processed);

-- 5. Create a similarity search function (RPC) for RAG Queries
CREATE OR REPLACE FUNCTION match_feedback (
  query_embedding vector(384),
  match_threshold float,
  match_count int
)
RETURNS TABLE (
  id bigint,
  alumni_speaker_name text,
  aspect_most_valuable text,
  improvements_suggestions text,
  future_topics text,
  session_rating integer,
  similarity float
)
LANGUAGE plpgsql AS $$
BEGIN
  RETURN QUERY
  SELECT
    dashboard_data.id,
    dashboard_data.alumni_speaker_name,
    dashboard_data.aspect_most_valuable,
    dashboard_data.improvements_suggestions,
    dashboard_data.future_topics,
    dashboard_data.session_rating,
    1 - (dashboard_data.embedding <=> query_embedding) AS similarity
  FROM dashboard_data
  WHERE dashboard_data.embedding IS NOT NULL 
    AND 1 - (dashboard_data.embedding <=> query_embedding) > match_threshold
  ORDER BY dashboard_data.embedding <=> query_embedding
  LIMIT match_count;
END;
$$;
