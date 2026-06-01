// Centralized API base URL. Override via VITE_API_URL env var for different environments.
// In dev, Vite proxies /api → :3000 (vite.config.mts) so use same-origin to avoid CORS / wrong-host issues.
const env = import.meta.env as { DEV?: boolean; VITE_API_URL?: string; VITE_APPLYR_API_TOKEN?: string };

export const API_BASE =
  env.VITE_API_URL ?? (env.DEV ? '' : `http://${window.location.hostname}:3000`);

export const api = (path: string) => `${API_BASE}${path}`;

function authHeaders(): Record<string, string> {
  const token = env.VITE_APPLYR_API_TOKEN;
  if (!token) return {};
  return { 'X-Applyr-Token': token };
}

/** Fetch with API base + optional Applyr token (must match server APPLYR_API_TOKEN when set). */
export async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  for (const [key, value] of Object.entries(authHeaders())) {
    if (!headers.has(key)) headers.set(key, value);
  }
  return fetch(api(path), { ...init, headers });
}

export async function apiJson<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await apiFetch(path, init);
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`API ${res.status}: ${detail || res.statusText}`);
  }
  return res.json() as Promise<T>;
}

/** Load jobs list; returns [] on failure so UI never treats an error object as an array. */
export async function fetchJobs(): Promise<unknown[]> {
  try {
    const res = await apiFetch('/api/jobs');
    if (!res.ok) {
      console.error('GET /api/jobs failed:', res.status, await res.text());
      return [];
    }
    const data = await res.json();
    return Array.isArray(data) ? data : [];
  } catch (err) {
    console.error('GET /api/jobs error:', err);
    return [];
  }
}
