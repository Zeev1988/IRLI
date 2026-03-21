-- Migrate embedding column from 1536 (OpenAI) to 1024 (FastEmbed BGE-Large).
-- Existing embeddings are discarded; they will be regenerated on next crawl.

drop index if exists lab_profiles_embedding_idx;

alter table lab_profiles add column embedding_new vector(1024);
alter table lab_profiles drop column embedding;
alter table lab_profiles rename column embedding_new to embedding;

create index lab_profiles_embedding_idx
    on lab_profiles
    using ivfflat (embedding vector_cosine_ops)
    with (lists = 100);
