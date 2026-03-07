-- Add technologies column for tools, software, methods, and instruments used by labs.
-- Run after 001_create_lab_profiles.sql.

alter table lab_profiles
    add column if not exists technologies text[] not null default '{}';
