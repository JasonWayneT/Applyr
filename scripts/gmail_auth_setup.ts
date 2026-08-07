// One-time local OAuth setup for CR-072 (Gmail job-search intake sync).
// Usage: npx tsx scripts/gmail_auth_setup.ts <path-to-downloaded-client-secret.json>
//
// Reads the Desktop-app OAuth client JSON downloaded from Google Cloud Console, walks Jason through
// browser-based consent for the gmail.readonly scope via the loopback redirect flow, and stores the
// client id/secret + refresh token in jobagent.sqlite's profiles table (key 'gmail_oauth'), per CR-015 —
// no .env file, no process.env fallback.

import Database from 'better-sqlite3';
import http from 'http';
import { exec } from 'child_process';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { google } from 'googleapis';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SCOPES = ['https://www.googleapis.com/auth/gmail.readonly'];

function loadClientSecret(jsonPath: string): { client_id: string; client_secret: string } {
  const raw = JSON.parse(fs.readFileSync(jsonPath, 'utf-8'));
  const creds = raw.installed || raw.web || raw;
  if (!creds?.client_id || !creds?.client_secret) {
    throw new Error(
      `Could not find client_id/client_secret in ${jsonPath}. Expected Google's downloaded ` +
        `"Desktop app" OAuth client JSON shape (top-level "installed" key).`,
    );
  }
  return { client_id: creds.client_id, client_secret: creds.client_secret };
}

function openBrowser(url: string) {
  const cmd = process.platform === 'win32' ? `start "" "${url}"` : `open "${url}"`;
  exec(cmd, () => {
    /* best-effort — the URL is printed either way */
  });
}

async function waitForAuthCode(port: number): Promise<string> {
  return new Promise((resolve, reject) => {
    const server = http.createServer((req, res) => {
      const url = new URL(req.url ?? '', `http://localhost:${port}`);
      const code = url.searchParams.get('code');
      const error = url.searchParams.get('error');

      res.setHeader('Content-Type', 'text/html');
      if (error) {
        res.end(`<html><body>Authorization failed: ${error}. You can close this window.</body></html>`);
        server.close();
        reject(new Error(`Google returned an error: ${error}`));
        return;
      }
      if (!code) {
        res.end('<html><body>No authorization code received. You can close this window.</body></html>');
        return;
      }
      res.end('<html><body>Authorization received — you can close this window and return to the terminal.</body></html>');
      server.close();
      resolve(code);
    });
    server.listen(port);
  });
}

async function main() {
  const jsonPath = process.argv[2];
  if (!jsonPath) {
    console.error('Usage: npx tsx scripts/gmail_auth_setup.ts <path-to-client-secret.json>');
    process.exit(1);
  }

  const { client_id, client_secret } = loadClientSecret(jsonPath);

  // Listen on an OS-assigned free port first, so the redirect_uri always matches a port that's
  // actually open — Desktop-app OAuth clients allow any localhost port for the loopback flow.
  const tempServer = http.createServer();
  await new Promise<void>((resolve) => tempServer.listen(0, resolve));
  const port = (tempServer.address() as { port: number }).port;
  tempServer.close();

  const redirectUri = `http://localhost:${port}`;
  const oauth2Client = new google.auth.OAuth2(client_id, client_secret, redirectUri);

  const authUrl = oauth2Client.generateAuthUrl({
    access_type: 'offline', // required to receive a refresh token, not just an access token
    prompt: 'consent',      // forces Google to re-issue a refresh token even on a repeat authorization
    scope: SCOPES,
  });

  console.log('\nOpening your browser to approve Gmail read access...');
  console.log(`If it doesn't open automatically, paste this URL into a browser:\n${authUrl}\n`);
  openBrowser(authUrl);

  const code = await waitForAuthCode(port);
  const { tokens } = await oauth2Client.getToken(code);

  if (!tokens.refresh_token) {
    console.error(
      '\nNo refresh token was returned. This usually means Google already has a prior grant for this ' +
        'client and skipped re-issuing one despite prompt=consent. Revoke existing access at ' +
        'https://myaccount.google.com/permissions (find "Applyr Gmail Sync") and re-run this script.',
    );
    process.exit(1);
  }

  const db = new Database(path.join(__dirname, '../data/jobagent.sqlite'));
  db.prepare('INSERT OR REPLACE INTO profiles (key, value) VALUES (?, ?)').run(
    'gmail_oauth',
    JSON.stringify({ client_id, client_secret, refresh_token: tokens.refresh_token }),
  );
  db.close();

  console.log('\nSuccess — Gmail OAuth credentials stored in jobagent.sqlite (profiles.gmail_oauth).');
}

main().catch((err) => {
  console.error('\nGmail auth setup failed:', err.message || err);
  process.exit(1);
});
