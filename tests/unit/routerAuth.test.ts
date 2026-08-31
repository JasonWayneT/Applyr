import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest';
import { Router } from 'express';
import { requireApiToken, isSafeHttpUrl, isValidJobId } from '../../server/middleware.js';

/* ------------------------------------------------------------------ */
/* requireApiToken — regression test for DEF-01 (systemRouter was       */
/* missing auth on its POST routes).  Ensures the middleware itself     */
/* rejects unauthenticated mutating requests when a token is configured. */
/* ------------------------------------------------------------------ */
describe('requireApiToken', () => {
  const origToken = process.env.APPLYR_API_TOKEN;

  afterEach(() => {
    if (origToken === undefined) delete process.env.APPLYR_API_TOKEN;
    else process.env.APPLYR_API_TOKEN = origToken;
  });

  function mockRes() {
    const res: any = { statusCode: 200, body: undefined, status(c: number) { this.statusCode = c; return this; }, json(b: unknown) { this.body = b; return this; } };
    return res;
  }

  it('allows GET requests without a token', () => {
    process.env.APPLYR_API_TOKEN = 'secret';
    const req = { method: 'GET', headers: {} } as any;
    const res = mockRes();
    let called = false;
    requireApiToken(req, res, () => { called = true; });
    expect(called).toBe(true);
    expect(res.statusCode).toBe(200);
  });

  it('rejects POST without X-Applyr-Token header when token is configured', () => {
    process.env.APPLYR_API_TOKEN = 'secret';
    const req = { method: 'POST', headers: {} } as any;
    const res = mockRes();
    let called = false;
    requireApiToken(req, res, () => { called = true; });
    expect(called).toBe(false);
    expect(res.statusCode).toBe(401);
    expect(res.body).toEqual({ error: 'Unauthorized' });
  });

  it('allows POST with correct X-Applyr-Token header', () => {
    process.env.APPLYR_API_TOKEN = 'secret';
    const req = { method: 'POST', headers: { 'x-applyr-token': 'secret' } } as any;
    const res = mockRes();
    let called = false;
    requireApiToken(req, res, () => { called = true; });
    expect(called).toBe(true);
    expect(res.statusCode).toBe(200);
  });

  it('allows all requests when no token is configured', () => {
    delete process.env.APPLYR_API_TOKEN;
    const req = { method: 'POST', headers: {} } as any;
    const res = mockRes();
    let called = false;
    requireApiToken(req, res, () => { called = true; });
    expect(called).toBe(true);
    expect(res.statusCode).toBe(200);
  });
});

/* ------------------------------------------------------------------ */
/* isSafeHttpUrl — regression test for DEF-02 (SSRF via local-model      */
/* endpoint).  Ensures non-http(s) protocols are rejected.             */
/* ------------------------------------------------------------------ */
describe('isSafeHttpUrl', () => {
  it('allows http and https URLs', () => {
    expect(isSafeHttpUrl('http://localhost:11434')).toBe(true);
    expect(isSafeHttpUrl('https://api.example.com/v1')).toBe(true);
  });

  it('rejects file:// URLs', () => {
    expect(isSafeHttpUrl('file:///etc/passwd')).toBe(false);
  });

  it('rejects javascript: URLs', () => {
    expect(isSafeHttpUrl('javascript:alert(1)')).toBe(false);
  });

  it('rejects malformed URLs', () => {
    expect(isSafeHttpUrl('not-a-url')).toBe(false);
    expect(isSafeHttpUrl('')).toBe(true); // empty = unset, allowed
    expect(isSafeHttpUrl(null)).toBe(true);
    expect(isSafeHttpUrl(undefined)).toBe(true);
  });
});

/* ------------------------------------------------------------------ */
/* isValidJobId — regression test for DEF-05 (ai-rewrite route          */
/* accepted unsanitized id).                                            */
/* ------------------------------------------------------------------ */
describe('isValidJobId', () => {
  it('accepts UUIDs', () => {
    expect(isValidJobId('550e8400-e29b-41d4-a716-446655440000')).toBe(true);
  });

  it('accepts alphanumeric, dash, underscore ids', () => {
    expect(isValidJobId('job_123')).toBe(true);
    expect(isValidJobId('company-name')).toBe(true);
  });

  it('rejects path traversal', () => {
    expect(isValidJobId('../etc/passwd')).toBe(false);
    expect(isValidJobId('foo/bar')).toBe(false);
    expect(isValidJobId('foo\\bar')).toBe(false);
  });

  it('rejects empty or overly long ids', () => {
    expect(isValidJobId('')).toBe(false);
    expect(isValidJobId('a'.repeat(129))).toBe(false);
  });
});
