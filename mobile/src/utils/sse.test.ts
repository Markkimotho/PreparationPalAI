import { createSseParser } from './sse';

test('frames split across chunks are reassembled', () => {
  const frames: unknown[] = [];
  const push = createSseParser(f => frames.push(f));
  push('data: {"type":"tok');
  push('en","text":"Hel"}\n\ndata: {"type":"token","text":"lo"}\n');
  push('\ndata: {"type":"done"}\n\n');
  expect(frames).toEqual([{ type: 'token', text: 'Hel' }, { type: 'token', text: 'lo' }, { type: 'done' }]);
});

test('comments, blank lines and non-JSON data are ignored', () => {
  const frames: unknown[] = [];
  const push = createSseParser(f => frames.push(f));
  push(': keep-alive\n\ndata: not json\n\ndata: {"type":"done"}\n\n');
  expect(frames).toEqual([{ type: 'done' }]);
});

test('carriage returns from proxies are tolerated', () => {
  const frames: unknown[] = [];
  createSseParser(f => frames.push(f))('data: {"type":"done"}\r\n\r\n');
  expect(frames).toEqual([{ type: 'done' }]);
});
