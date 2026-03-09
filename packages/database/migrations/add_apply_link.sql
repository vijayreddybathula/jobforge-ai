-- Migration: add apply_link column to jobs_raw
-- Run once after deploying this version.
-- Safe to run multiple times (IF NOT EXISTS guard).
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='jobs_raw' AND column_name='apply_link'
    ) THEN
        ALTER TABLE jobs_raw ADD COLUMN apply_link VARCHAR(1000);
    END IF;
END$$;
