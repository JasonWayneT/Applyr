/** Parse Server-Sent Event blocks from a growing text buffer (CR-ARCH-006). */
export type SseEvent<T = unknown> = { event: string; data: T };

export function parseSseChunk(buffer: string): { events: SseEvent[]; remainder: string } {
  const events: SseEvent[] = [];
  const blocks = buffer.split('\n\n');
  const remainder = blocks.pop() ?? '';

  for (const block of blocks) {
    if (!block.startsWith('event:')) continue;
    const lines = block.split('\n');
    const eventName = lines[0].replace('event: ', '').trim();
    const dataLine = lines.find((l) => l.startsWith('data:'));
    if (!dataLine) continue;
    try {
      const data = JSON.parse(dataLine.replace(/^data: /, ''));
      events.push({ event: eventName, data });
    } catch {
      // Non-JSON payload — skip
    }
  }

  return { events, remainder };
}
