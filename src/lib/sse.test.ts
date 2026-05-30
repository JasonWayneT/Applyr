import { describe, expect, it } from 'vitest';
import { parseSseChunk } from './sse';

describe('parseSseChunk', () => {
  it('parses a single complete event block', () => {
    const chunk = 'event: stage\ndata: {"id":"gate","status":"running"}\n\n';
    const { events, remainder } = parseSseChunk(chunk);
    expect(remainder).toBe('');
    expect(events).toHaveLength(1);
    expect(events[0].event).toBe('stage');
    expect(events[0].data).toEqual({ id: 'gate', status: 'running' });
  });

  it('buffers partial blocks across chunks', () => {
    const first = parseSseChunk('event: done\ndata: {"passed":');
    expect(first.events).toHaveLength(0);
    expect(first.remainder).toContain('event: done');

    const second = parseSseChunk(`${first.remainder}true}\n\n`);
    expect(second.events).toHaveLength(1);
    expect(second.events[0].event).toBe('done');
    expect(second.events[0].data).toEqual({ passed: true });
  });

  it('parses multiple events in one chunk', () => {
    const chunk =
      'event: log\ndata: {"message":"hi"}\n\n' +
      'event: done\ndata: {"exitCode":0}\n\n';
    const { events } = parseSseChunk(chunk);
    expect(events.map((e) => e.event)).toEqual(['log', 'done']);
  });
});
