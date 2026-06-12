INSERT OR IGNORE INTO sources (id, name, type, provider, base_url, status) VALUES
  ('ashby',      'Ashby',      'ats_api',    'Ashby',      'https://api.ashbyhq.com/v1/publishing-posts', 'active'),
  ('workable',   'Workable',   'ats_api',    'Workable',   'https://www.workable.com/api/accounts',       'active'),
  ('theirstack', 'TheirStack', 'vendor_api', 'TheirStack', 'https://api.theirstack.com/v1/jobs',           'active');
