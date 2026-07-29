import { spawn } from 'child_process';

const DEFAULT_BASE_URL = 'http://localhost:11434';
const POLL_MS = 2000;
const STARTUP_TIMEOUT_MS = 45_000;

export function resolveOllamaBaseUrl(explicit?: string): string {
  const fromEnv = process.env.OLLAMA_HOST?.trim();
  if (explicit?.trim()) return explicit.trim().replace(/\/$/, '');
  if (fromEnv) return fromEnv.replace(/\/$/, '');
  return DEFAULT_BASE_URL;
}

export function isOllamaAutoStartEnabled(): boolean {
  const flag = (process.env.OLLAMA_AUTO_START ?? '1').toLowerCase();
  return !['0', 'false', 'no', 'off'].includes(flag);
}

async function pingOllama(baseUrl: string, timeoutMs = 2500): Promise<boolean> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(`${baseUrl}/api/tags`, { signal: controller.signal });
    return res.ok;
  } catch {
    return false;
  } finally {
    clearTimeout(timer);
  }
}

function spawnOllamaServe(onLog?: (msg: string) => void): void {
  onLog?.('Ollama not reachable — starting `ollama serve` in background.');
  const child = spawn('ollama', ['serve'], {
    detached: true,
    stdio: 'ignore',
    windowsHide: true,
    shell: process.platform === 'win32',
  });
  child.unref();
  child.on('error', (err) => {
    onLog?.(`Failed to spawn ollama serve: ${err.message}`);
  });
}

/**
 * Ensure local Ollama responds before evaluate/draft stages.
 * Starts `ollama serve` when auto-start is enabled and nothing listens on the base URL.
 */
export async function ensureOllamaReady(options: {
  baseUrl?: string;
  onLog?: (msg: string) => void;
  autoStart?: boolean;
} = {}): Promise<void> {
  const baseUrl = resolveOllamaBaseUrl(options.baseUrl);
  const onLog = options.onLog;
  const autoStart = options.autoStart ?? isOllamaAutoStartEnabled();

  if (await pingOllama(baseUrl)) {
    onLog?.(`Ollama ready at ${baseUrl}.`);
    return;
  }

  if (!autoStart) {
    throw new Error(
      `Ollama is not running at ${baseUrl} and OLLAMA_AUTO_START is disabled. Start Ollama manually.`,
    );
  }

  spawnOllamaServe(onLog);

  const deadline = Date.now() + STARTUP_TIMEOUT_MS;
  while (Date.now() < deadline) {
    await new Promise((r) => setTimeout(r, POLL_MS));
    if (await pingOllama(baseUrl)) {
      onLog?.(`Ollama started and ready at ${baseUrl}.`);
      return;
    }
  }

  throw new Error(
    `Ollama did not become ready at ${baseUrl} within ${STARTUP_TIMEOUT_MS / 1000}s. ` +
      'Install Ollama and ensure `ollama` is on PATH, or start it manually.',
  );
}
