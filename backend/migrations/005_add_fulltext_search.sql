-- Hybrid search: add tsvector + GIN for BM25-style keyword search.
-- Combine with pgvector similarity for hybrid ranking.

-- 1. Generated column: searchable text from keywords, technologies, research_summary, etc.
alter table lab_profiles
add column if not exists search_vector tsvector
generated always as (
    setweight(to_tsvector('english', coalesce(pi_name, '')), 'A')
    || setweight(to_tsvector('english', coalesce(institution, '')), 'B')
    || setweight(to_tsvector('english', coalesce(faculty, '')), 'B')
    || setweight(to_tsvector('english', coalesce(array_to_string(research_summary, ' '), '')), 'A')
    || setweight(to_tsvector('english', coalesce(array_to_string(keywords, ' '), '')), 'A')
    || setweight(to_tsvector('english', coalesce(array_to_string(technologies, ' '), '')), 'B')
) stored;

-- 2. GIN index for fast full-text search
create index if not exists lab_profiles_search_vector_idx
    on lab_profiles using gin (search_vector);
