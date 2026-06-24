# Security Policy

## Reporting a vulnerability

If you discover a security issue, report it privately before opening a public GitHub issue.

## Secrets and personal data

- API keys belong in **Settings → API or Connections** (stored in local `jobagent.sqlite` only).
- Never commit `.env`, `data/jobagent.sqlite`, `data/submissions/`, `data/archive/`, or personal files under `data/` (except `*.example.*` templates).
- Run `python scripts/audit_public_repo.py` before pushing to a public remote.

## Fresh clone setup

```bash
python scripts/bootstrap_local_data.py
```

Then configure profile, experience, and API keys through the UI.

## Compromised history

If you forked an older revision that contained personal data or API keys, treat any exposed keys as compromised and rotate them immediately.
