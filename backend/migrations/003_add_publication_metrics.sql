-- Add publication metrics from Semantic Scholar.
-- Run after 002_add_technologies.sql.

ALTER TABLE lab_profiles
    ADD COLUMN IF NOT EXISTS publication_count int,
    ADD COLUMN IF NOT EXISTS citation_count int,
    ADD COLUMN IF NOT EXISTS h_index int,
    ADD COLUMN IF NOT EXISTS semantic_scholar_author_id text,
    ADD COLUMN IF NOT EXISTS metrics_updated_at timestamptz;
