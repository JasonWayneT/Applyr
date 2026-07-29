/**
 * Unified subprocess spawning (CR-ARCH-004). Transport only — no line parsing here.
 */
import { spawn, type ChildProcess, type ChildProcessWithoutNullStreams } from 'child_process';
import path from 'path';
import { resolvePythonExecutable } from '../domain/pythonBin.js';
import { PROJECT_ROOT, SCRIPTS_DIR, buildPythonEnv } from '../shared.js';

const SECRET_ENV_KEYS = new Set([
  'GEMINI_API_KEY',
  'GOOGLE_API_KEY',
  'ANTHROPIC_API_KEY',
  'PERPLEXITY_API_KEY',
  'OPENAI_API_KEY',
  'ADZUNA_APP_KEY',
  'ADZUNA_APP_ID',
]);

export function pythonScriptPath(scriptName: string): string {
  return path.join(SCRIPTS_DIR, scriptName);
}

export { resolvePythonExecutable } from '../domain/pythonBin.js';

export function buildSpawnEnv(extra: Record<string, string> = {}): Record<string, string> {
  const env: Record<string, string> = { ...buildPythonEnv(), ...extra };
  for (const [key, value] of Object.entries(process.env)) {
    if (value === undefined || SECRET_ENV_KEYS.has(key)) continue;
    if (key.startsWith('npm_') || key.startsWith('NODE_')) continue;
    // Never inherit another project's venv (e.g. Hermes) into Applyr child processes.
    if (key === 'VIRTUAL_ENV' || key === 'PYTHONHOME') continue;
    env[key] = value;
  }
  return env;
}

export function runBuffered(
  args: string[],
  options: { cwd?: string; env?: Record<string, string>; stdin?: string } = {},
): Promise<{ code: number; stdout: string; stderr: string }> {
  return new Promise((resolve, reject) => {
    const proc = spawn(resolvePythonExecutable(), args, {
      cwd: options.cwd ?? PROJECT_ROOT,
      shell: false,
      env: options.env ?? buildSpawnEnv(),
    });

    let stdout = '';
    let stderr = '';
    proc.stdout.on('data', (chunk: Buffer) => { stdout += chunk.toString(); });
    proc.stderr.on('data', (chunk: Buffer) => { stderr += chunk.toString(); });
    if (options.stdin !== undefined) {
      proc.stdin.write(options.stdin);
    }
    proc.stdin.end();

    proc.on('error', reject);
    proc.on('close', (code) => resolve({ code: code ?? 1, stdout, stderr }));
  });
}

/** Stream stdout/stderr by line chunks; scout keeps parsers in scout.ts */
export function runStreamLines(
  command: string,
  args: string[],
  options: {
    cwd?: string;
    env?: Record<string, string>;
    onStdout: (chunk: string) => void;
    onStderr: (chunk: string) => void;
  },
): Promise<number> {
  return new Promise((resolve, reject) => {
    try {
      const child = spawn(command, args, {
        cwd: options.cwd ?? PROJECT_ROOT,
        shell: false,
        env: buildSpawnEnv(options.env ?? {}),
      });

      child.stdout.on('data', (chunk) => options.onStdout(chunk.toString()));
      child.stderr.on('data', (chunk) => options.onStderr(chunk.toString()));

      child.on('close', (code) => resolve(code ?? 1));
      child.on('error', (err) => reject(err));
    } catch (err) {
      reject(err);
    }
  });
}

export function runDetached(
  args: string[],
  options: { cwd?: string; env?: Record<string, string> } = {},
): ChildProcess {
  const proc = spawn(resolvePythonExecutable(), args, {
    cwd: options.cwd ?? PROJECT_ROOT,
    shell: false,
    env: buildSpawnEnv(options.env ?? {}),
    detached: true,
    stdio: 'ignore',
  });
  proc.unref();
  return proc;
}

/** Interactive python child (SSE evaluate, manual draft) — caller may attachClientAbort */
export function spawnPython(
  args: string[],
  options: {
    cwd?: string;
    env?: Record<string, string>;
    stdin?: string;
    onStdout?: (chunk: string) => void;
    onStderr?: (chunk: string) => void;
    onClose?: (code: number | null) => void;
    onError?: (err: Error) => void;
  } = {},
): ChildProcessWithoutNullStreams {
  const proc = spawn(resolvePythonExecutable(), args, {
    cwd: options.cwd ?? PROJECT_ROOT,
    shell: false,
    env: buildSpawnEnv(options.env),
  });

  if (options.stdin !== undefined) {
    proc.stdin.write(options.stdin);
  }
  proc.stdin.end();

  if (options.onStdout) {
    proc.stdout.on('data', (chunk: Buffer) => options.onStdout!(chunk.toString()));
  }
  if (options.onStderr) {
    proc.stderr.on('data', (chunk: Buffer) => options.onStderr!(chunk.toString()));
  }
  if (options.onClose) {
    proc.on('close', (code) => options.onClose!(code));
  }
  if (options.onError) {
    proc.on('error', (err) => options.onError!(err));
  }

  return proc;
}
