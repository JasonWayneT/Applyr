-- Migration 012_add_tracking_columns.sql
ALTER TABLE jobs ADD COLUMN user_edits_count INTEGER DEFAULT 0;
ALTER TABLE jobs ADD COLUMN screening_reached BOOLEAN DEFAULT 0;
ALTER TABLE jobs ADD COLUMN hm_interview_reached BOOLEAN DEFAULT 0;
