import fs from 'fs';
import path from 'path';
import { PROJECT_ROOT } from '../shared.js';

/** Project-local venv interpreter (never Hermes / global PATH). */
export const APPLYR_VENV_PYTHON =
  process.platform === 'win32'
    ? path.join(PROJECT_ROOT, '.venv', 'Scripts', 'python.exe')
    : path.join(PROJECT_ROOT, '.venv', 'bin', 'python');

const SETUP_HINT =
  'Run `npm run setup:python` from the Applyr project root to create .venv and install dependencies.';

let cachedPython: string | null = null;

function assertExecutable(pythonPath: string): string {
  if (pythonPath.toLowerCase().includes('hermes')) {
    throw new Error(
      `Refusing Hermes Python for Applyr: ${pythonPath}. ${SETUP_HINT}`,
    );
  }
  if (!fs.existsSync(pythonPath)) {
    throw new Error(`Python interpreter not found at ${pythonPath}. ${SETUP_HINT}`);
  }
  return pythonPath;
}

/**
 * Resolve the Python binary Applyr must use for all pipeline spawns.
 * Priority: APPLYR_PYTHON env → project .venv → error (never bare PATH `python`).
 */
export function resolvePythonExecutable(): string {
  if (cachedPython) return cachedPython;

  const explicit = process.env.APPLYR_PYTHON?.trim();
  if (explicit) {
    cachedPython = assertExecutable(explicit);
    return cachedPython;
  }

  if (fs.existsSync(APPLYR_VENV_PYTHON)) {
    cachedPython = assertExecutable(APPLYR_VENV_PYTHON);
    return cachedPython;
  }

  throw new Error(
    `Applyr Python environment missing (.venv not found at ${APPLYR_VENV_PYTHON}). ${SETUP_HINT}`,
  );
}

/** Clear module cache (tests only). */
export function resetPythonExecutableCache(): void {
  cachedPython = null;
}
