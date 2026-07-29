import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  ensureOllamaReady,
  isOllamaAutoStartEnabled,
  resolveOllamaBaseUrl,
} from '../../server/services/ollamaLifecycle.js';

describe('ollamaLifecycle', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    delete process.env.OLLAMA_HOST;
    delete process.env.OLLAMA_AUTO_START;
  });

  it('resolveOllamaBaseUrl prefers explicit then env', () => {
    process.env.OLLAMA_HOST = 'http://127.0.0.1:11434/';
    expect(resolveOllamaBaseUrl('http://custom:9999/')).toBe('http://custom:9999');
    expect(resolveOllamaBaseUrl()).toBe('http://127.0.0.1:11434');
  });

  it('returns immediately when ollama already responds', async () => {
    vi.mocked(fetch).mockResolvedValue({ ok: true } as Response);
    const logs: string[] = [];
    await ensureOllamaReady({
      baseUrl: 'http://localhost:11434',
      autoStart: false,
      onLog: (m) => logs.push(m),
    });
    expect(logs.some((l) => l.includes('Ollama ready'))).toBe(true);
    expect(fetch).toHaveBeenCalled();
  });

  it('isOllamaAutoStartEnabled respects env flag', () => {
    process.env.OLLAMA_AUTO_START = '0';
    expect(isOllamaAutoStartEnabled()).toBe(false);
    process.env.OLLAMA_AUTO_START = '1';
    expect(isOllamaAutoStartEnabled()).toBe(true);
  });
});
