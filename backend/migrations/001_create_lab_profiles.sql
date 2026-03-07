-- Run this once in the Supabase SQL editor (or any PostgreSQL client).
-- Requires PostgreSQL >= 15 and the pgvector extension available in Supabase.

-- 1. Enable pgvector
create extension if not exists vector;

-- 2. Main table
create table if not exists lab_profiles (
    id              bigserial primary key,

    -- Core fields matching LabProfile schema
    pi_name         text        not null,
    institution     text        not null,
    faculty         text        not null,
    research_summary text[]     not null,   -- array of 2-5 bullet strings
    keywords        text[]      not null,   -- array of 3-8 tags
    hiring_status   text        not null,   -- "true", "false", or descriptive string
    lab_url         text        not null,

    -- Semantic search
    embedding       vector(1536),           -- OpenAI text-embedding-3-small

    -- Housekeeping
    last_crawled_at timestamptz not null default now(),
    created_at      timestamptz not null default now(),

    constraint lab_profiles_lab_url_unique unique (lab_url)
);

-- 3. IVFFlat index for fast approximate nearest-neighbour search
--    (cosine distance — best for normalised OpenAI embeddings)
--    lists = sqrt(expected row count); start with 100 and tune later.
create index if not exists lab_profiles_embedding_idx
    on lab_profiles
    using ivfflat (embedding vector_cosine_ops)
    with (lists = 100);

-- 4. Index for fast recency queries
create index if not exists lab_profiles_crawled_idx
    on lab_profiles (last_crawled_at desc);
