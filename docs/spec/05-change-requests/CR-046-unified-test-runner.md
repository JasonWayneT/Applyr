# CR-046: Unified Test Runner

## Metadata
| Field | Value |
|---|---|
| **CR ID** | `CR-046` |
| **Date** | 2026-06-11 |
| **Status** | Accepted |
| **Priority** | P1 |
| **Implements** | `FR-241` |

## Problem statement
The project contains two test suites: a Vitest TypeScript suite and various Python unit/regression test scripts. There is no unified way to run both suites in a single command, making it easy to miss test failures before checking in code. 

Additionally, running Python tests inside a unified test runner can encounter Windows code-page decoding issues if non-ASCII output is emitted, and invoking `npm test` recursively from tests like `test_smoke_regression.py` can cause infinite loop errors.

## Solution
1. Create a Python-based unified test runner `scripts/run_all_tests.py` that runs both the Python unit tests and the Vitest test suite.
2. Ensure the runner executes Python subprocesses with `PYTHONIOENCODING=utf-8` and decodes text streams with `errors="replace"` to handle non-ASCII/em-dash characters on Windows.
3. Link the `npm test` script in `package.json` to our unified test runner.
4. Modify `scripts/test_smoke_regression.py` to call `npx vitest run` directly (rather than `npm test`) to avoid recursive execution loop.
5. Fix `scripts/test_candidate_context.py` and `scripts/test_resume_conversion_eval.py` to correctly mock the local database/catalog state and prevent test failure leaks.

## Acceptance criteria
| AC ID | Given | When | Then |
|---|---|---|---|
| `AC-215` | Both Python and Vitest test suites pass | Running `python scripts/run_all_tests.py` | Command succeeds with exit code 0 and displays a summary table |
| `AC-216` | A Python unit test or Vitest suite fails | Running `python scripts/run_all_tests.py` | Command fails with exit code 1 and prints the failure output |
| `AC-217` | Standard terminal shell | Running `npm test` | Invokes `python scripts/run_all_tests.py` to run both suites |
| `AC-218` | Windows terminal with cp1252/cp437 | Tests print ellipsis/non-ASCII output | Captured correctly by the unified runner without throwing a UnicodeDecodeError |
| `AC-219` | Running regression tests | Subprocess executes Vitest target | Runs `npx vitest run` directly without recurse-looping `npm test` |
