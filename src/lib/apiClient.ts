import { api } from './api';

const API_TOKEN = (import.meta as { env?: { VITE_APPLYR_API_TOKEN?: string } }).env?.VITE_APPLYR_API_TOKEN;

function authHeaders(): Record<string, string> {
  if (!API_TOKEN) return {};
  return { 'X-Applyr-Token': API_TOKEN };
}

/** Fetch with API base URL and optional Applyr token (CR-ARCH-006). */
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
