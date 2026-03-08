-- Observability: track ingestion runs per faculty index URL.
CREATE TABLE IF NOT EXISTS ingestion_logs (
    id              BIGSERIAL PRIMARY KEY,
    index_url       TEXT NOT NULL,
    started_at      TIMESTAMPTZ NOT NULL,
    finished_at     TIMESTAMPTZ,
    success_count   INT DEFAULT 0,
    failed_count    INT DEFAULT 0,
    error_message   TEXT
);

CREATE INDEX IF NOT EXISTS ingestion_logs_index_url_idx ON ingestion_logs (index_url);
CREATE INDEX IF NOT EXISTS ingestion_logs_started_at_idx ON ingestion_logs (started_at DESC);
