-- Enable pg_trgm for fuzzy matching (yosi -> yossi, telaviv -> tel aviv).
-- Required for token-based search typo tolerance.
create extension if not exists pg_trgm;
