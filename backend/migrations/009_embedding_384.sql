-- Migrate embedding column from 1024 (BGE-Large) to 384 (BGE-Small).
-- Existing embeddings are discarded; they will be regenerated on next crawl.

drop index if exists lab_profiles_embedding_idx;

alter table lab_profiles add column embedding_new vector(384);
alter table lab_profiles drop column embedding;
alter table lab_profiles rename column embedding_new to embedding;

create index lab_profiles_embedding_idx
    on lab_profiles
    using ivfflat (embedding vector_cosine_ops)
    with (lists = 100);
