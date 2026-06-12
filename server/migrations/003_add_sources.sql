CREATE TABLE IF NOT EXISTS sources (
  id                      TEXT PRIMARY KEY,
  name                    TEXT NOT NULL,
  type                    TEXT NOT NULL CHECK(type IN ('ats_api', 'vendor_api', 'crawl')),
  provider                TEXT,
  base_url                TEXT,
  auth_details            TEXT,
  poll_frequency_hours    INTEGER,
  status                  TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active', 'warning', 'error', 'paused')),
  last_success_at         TEXT,
  last_error_at           TEXT,
  consecutive_failures    INTEGER NOT NULL DEFAULT 0,
  credits_used_this_month INTEGER NOT NULL DEFAULT 0,
  credits_reset_at        TEXT
);

INSERT OR IGNORE INTO sources (id, name, type, provider, base_url, status) VALUES
  ('remotive',       'Remotive',        'vendor_api', 'Remotive',        'https://remotive.com/api/remote-jobs',                  'active'),
  ('remoteok',       'RemoteOK',        'vendor_api', 'RemoteOK',        'https://remoteok.com/api',                              'active'),
  ('weworkremotely', 'We Work Remotely','vendor_api', 'We Work Remotely','https://weworkremotely.com/categories/remote-product-jobs.rss', 'active'),
  ('himalayas',      'Himalayas',       'vendor_api', 'Himalayas',       'https://himalayas.app/jobs/api',                        'active'),
  ('themuse',        'The Muse',        'vendor_api', 'The Muse',        'https://www.themuse.com/api/public/jobs',                'active'),
  ('jobicy',         'Jobicy',          'vendor_api', 'Jobicy',          'https://jobicy.com/api/v2/remote-jobs',                  'active'),
  ('workingnomads',  'Working Nomads',  'vendor_api', 'Working Nomads',  'https://www.workingnomads.com/api/exposed_jobs/',        'active'),
  ('jobscollider',   'JobsCollider',    'vendor_api', 'JobsCollider',    'https://remotefirstjobs.com/remote-product-jobs.rss',    'active'),
  ('adzuna',         'Adzuna',          'vendor_api', 'Adzuna',          'https://api.adzuna.com/v1/api/jobs',                    'active'),
  ('openpostings',   'OpenPostings',    'vendor_api', 'OpenPostings',    'http://localhost:8787',                                  'active'),
  ('builtin',        'Built In',        'crawl',      'Built In',        'https://builtin.com',                                   'active'),
  ('levelsfyi',      'Levels.fyi',      'crawl',      'Levels.fyi',      'https://www.levels.fyi',                                'active');
