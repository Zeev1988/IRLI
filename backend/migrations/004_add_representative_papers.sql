-- Representative papers for disambiguating authors in Semantic Scholar
-- Used by the "Known Paper" strategy when affiliations are missing
-- Run after 003_add_publication_metrics.sql
ALTER TABLE lab_profiles
  ADD COLUMN representative_papers text[] NOT NULL DEFAULT '{}';
