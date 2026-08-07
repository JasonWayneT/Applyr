import type BetterSqlite3 from 'better-sqlite3';
import { google, gmail_v1 } from 'googleapis';

export interface GmailClient {
  /** Resolves labelName (e.g. "Applyr/Incoming") to its id and lists all message ids under it. Throws if
   *  the label doesn't exist — this is a hard requirement for the caller's core loop. */
  listMessageIdsUnderLabel(labelName: string): Promise<string[]>;
  /** Fetches one message in full format (headers, snippet, internalDate, labelIds). */
  getMessage(messageId: string): Promise<gmail_v1.Schema$Message>;
  /** Non-throwing label name -> id lookup, for optional/diagnostic checks (e.g. CR-072's dry-run
   *  label-agreement field) where a missing label should degrade to "unknown," not crash the sync. */
  resolveLabelId(labelName: string): Promise<string | null>;
}

interface StoredGmailOAuth {
  client_id: string;
  client_secret: string;
  refresh_token: string;
}

function loadStoredCredentials(db: BetterSqlite3.Database): StoredGmailOAuth {
  const row = db.prepare('SELECT value FROM profiles WHERE key = ?').get('gmail_oauth') as
    | { value: string }
    | undefined;
  if (!row) {
    throw new Error(
      'No gmail_oauth credentials in profiles table — run scripts/gmail_auth_setup.ts first (CR-072 Epic 1).',
    );
  }
  return JSON.parse(row.value) as StoredGmailOAuth;
}

export function createGmailClient(db: BetterSqlite3.Database): GmailClient {
  const { client_id, client_secret, refresh_token } = loadStoredCredentials(db);

  const auth = new google.auth.OAuth2(client_id, client_secret);
  auth.setCredentials({ refresh_token });
  // No access_token/expiry_date set — google-auth-library transparently fetches and caches a fresh
  // access token from the refresh_token on first use, and again whenever it expires. No DB write needed
  // on refresh: the refresh_token itself doesn't rotate for this grant type, only short-lived access
  // tokens do, and those don't need to survive a process restart.

  const gmail = google.gmail({ version: 'v1', auth });

  // Fetched and cached once (not once per distinct label name) — labels.list already returns every
  // label in one call, so there's no reason to re-fetch it per name requested.
  let labelIdCache: Map<string, string> | null = null;

  async function loadLabelIdMap(): Promise<Map<string, string>> {
    if (labelIdCache) return labelIdCache;
    const { data } = await gmail.users.labels.list({ userId: 'me' });
    labelIdCache = new Map((data.labels ?? []).filter((l) => l.name && l.id).map((l) => [l.name!, l.id!]));
    return labelIdCache;
  }

  async function resolveLabelId(labelName: string): Promise<string | null> {
    const map = await loadLabelIdMap();
    return map.get(labelName) ?? null;
  }

  async function listMessageIdsUnderLabel(labelName: string): Promise<string[]> {
    const labelId = await resolveLabelId(labelName);
    if (!labelId) {
      throw new Error(`Gmail label "${labelName}" not found on this account.`);
    }
    const ids: string[] = [];
    let pageToken: string | undefined;

    do {
      const { data } = await gmail.users.messages.list({
        userId: 'me',
        labelIds: [labelId],
        maxResults: 100,
        pageToken,
      });
      ids.push(...(data.messages ?? []).map((m) => m.id!).filter(Boolean));
      pageToken = data.nextPageToken ?? undefined;
    } while (pageToken);

    return ids;
  }

  async function getMessage(messageId: string): Promise<gmail_v1.Schema$Message> {
    const { data } = await gmail.users.messages.get({
      userId: 'me',
      id: messageId,
      format: 'full',
    });
    return data;
  }

  return { listMessageIdsUnderLabel, getMessage, resolveLabelId };
}
