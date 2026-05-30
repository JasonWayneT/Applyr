import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export const PROJECT_ROOT = path.join(__dirname, '../..');
export const CANDIDATE_PREFS_PATH = path.join(PROJECT_ROOT, 'data/candidate_preferences.json');

export const DATE_POSTED_TO_DAYS: Record<string, number> = {
  'Past 24 hours': 1,
  'Past 3 days': 3,
  'Past week': 7,
  'Past month': 30,
};
