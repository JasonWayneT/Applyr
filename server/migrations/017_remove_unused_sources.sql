-- Jason-directed (2026-08-30): he doesn't use jobs sourced from remotefirstjobs.com
-- (the "jobscollider" source) or weworkremotely.com. Both connectors are removed from
-- scoutOrchestrator.ts's buildDefaultConnectors() and their packages/connectors/*
-- folders deleted; this removes the matching rows so Settings' Data Sources list
-- stops showing two sources that can no longer actually run.
-- Data-only cleanup, no schema change.
DELETE FROM sources WHERE id IN ('jobscollider', 'weworkremotely');
