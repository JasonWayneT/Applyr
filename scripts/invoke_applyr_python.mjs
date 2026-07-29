/**
 * Run a Python script with Applyr's project .venv (never PATH `python` / Hermes).
 * Usage: node scripts/invoke_applyr_python.mjs scripts/run_all_tests.py [--flags]
 */
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.join(__dirname, '..');

function resolveApplyrPython() {
  const explicit = process.env.APPLYR_PYTHON?.trim();
  if (explicit) {
    if (!fs.existsSync(explicit)) {
      console.error(`APPLYR_PYTHON not found: ${explicit}`);
      process.exit(1);
    }
    return explicit;
  }

  const venvPython =
    process.platform === 'win32'
      ? path.join(ROOT, '.venv', 'Scripts', 'python.exe')
      : path.join(ROOT, '.venv', 'bin', 'python');

  if (fs.existsSync(venvPython)) {
    if (venvPython.toLowerCase().includes('hermes')) {
      console.error(`Refusing Hermes Python: ${venvPython}`);
      process.exit(1);
    }
    return venvPython;
  }

  console.error(
    'Applyr .venv not found. Run: npm run setup:python\n' +
      `Expected: ${venvPython}`,
  );
  process.exit(1);
}

const [, , scriptRel, ...scriptArgs] = process.argv;
if (!scriptRel) {
  console.error('Usage: node scripts/invoke_applyr_python.mjs <script.py> [args...]');
  process.exit(1);
}

const scriptPath = path.isAbsolute(scriptRel) ? scriptRel : path.join(ROOT, scriptRel);
const python = resolveApplyrPython();
const result = spawnSync(python, [scriptPath, ...scriptArgs], {
  cwd: ROOT,
  stdio: 'inherit',
  env: { ...process.env, PYTHONUNBUFFERED: '1' },
});
process.exit(result.status ?? 1);
