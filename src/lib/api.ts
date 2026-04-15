// Centralized API base URL. Override via VITE_API_URL env var for different environments.
const API_BASE = (import.meta as any).env?.VITE_API_URL ?? 'http://localhost:3000';

export const api = (path: string) => `${API_BASE}${path}`;
