-- CR-114 / FR-329 / AC-427:
-- Surface why Stage 0 paused: decision basis and uncertainty, alongside the
-- existing requirement and evidence excerpt. Additive columns only.

ALTER TABLE pending_skill_confirmations ADD COLUMN decision_basis TEXT;
ALTER TABLE pending_skill_confirmations ADD COLUMN uncertainty TEXT;
