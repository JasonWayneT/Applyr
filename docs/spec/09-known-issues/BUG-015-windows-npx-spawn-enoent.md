# BUG-015: Job Sync Fails on Windows with `spawn npx ENOENT`

## Metadata

- Bug ID: `BUG-015`
- Status: fixed
- Severity: high
- Component: `server/scout.ts`, `server/shared.ts`
- Related requirements: `FR-164`

## Description

Starting a full job sync (`POST /api/sync`) on Windows immediately stops with:

`Sync stopped: spawn npx ENOENT`

The scout pipeline never runs Stage 1.

## Root cause

`runScoutSync` spawned subprocesses with `spawn('npx', ['tsx', ...], { shell: false })`. On Windows, `npx` is a PowerShell/cmd shim (`.ps1` / `.cmd`), not an executable Node can launch without `shell: true`. Node reports `ENOENT`.

## Fix

Spawn the project-local `tsx` CLI via `process.execPath` and `node_modules/tsx/dist/cli.mjs` (same pattern as `node_modules/.bin/tsx.cmd`), preserving array args and `shell: false` per `FR-164`.

## Verification

On Windows, trigger sync; Stage 1 log lines from `scout_local.ts` appear instead of immediate `spawn npx ENOENT`.
