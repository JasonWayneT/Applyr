import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import fs from 'fs';
import os from 'os';
import path from 'path';
import {
  APPLYR_VENV_PYTHON,
  resetPythonExecutableCache,
  resolvePythonExecutable,
} from '../../server/domain/pythonBin.js';

describe('pythonBin', () => {
  const originalApplyrPython = process.env.APPLYR_PYTHON;

  beforeEach(() => {
    resetPythonExecutableCache();
  });

  afterEach(() => {
    resetPythonExecutableCache();
    if (originalApplyrPython === undefined) {
      delete process.env.APPLYR_PYTHON;
    } else {
      process.env.APPLYR_PYTHON = originalApplyrPython;
    }
  });

  it('prefers APPLYR_PYTHON when set', () => {
    const tmp = path.join(os.tmpdir(), `applyr-python-test-${process.pid}.txt`);
    fs.writeFileSync(tmp, '');
    process.env.APPLYR_PYTHON = tmp;
    expect(resolvePythonExecutable()).toBe(tmp);
    fs.unlinkSync(tmp);
  });

  it('uses project .venv when present', () => {
    if (!fs.existsSync(APPLYR_VENV_PYTHON)) {
      expect(() => resolvePythonExecutable()).toThrow(/Applyr Python environment missing/);
      return;
    }
    expect(resolvePythonExecutable()).toBe(APPLYR_VENV_PYTHON);
  });

  it('refuses Hermes via APPLYR_PYTHON', () => {
    process.env.APPLYR_PYTHON = 'C:\\Users\\Jason\\AppData\\Local\\hermes\\hermes-agent\\venv\\Scripts\\python.exe';
    expect(() => resolvePythonExecutable()).toThrow(/Refusing Hermes Python/);
  });
});
