jest.mock('./session', () => ({ accessToken: jest.fn(async () => 'jwt-1') }));
import * as session from './session';
import { ApiError, getJson, onSignedOut, postJson, stream } from './api';

const response = (status: number, body: unknown) => ({ ok: status < 400, status, statusText: 'x', json: async () => body });

beforeEach(() => { jest.clearAllMocks(); (session.accessToken as jest.Mock).mockResolvedValue('jwt-1'); });

test('requests carry the access token', async () => {
  const fetchMock = jest.fn(async () => response(200, { decks: [] }));
  global.fetch = fetchMock as unknown as typeof fetch;
  await getJson('/api/flashcards');
  const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
  expect(url).toMatch(/\/api\/flashcards$/);
  expect((init.headers as Record<string, string>).Authorization).toBe('Bearer jwt-1');
});

test('a 401 or a missing token tells the app to sign in again', async () => {
  const signedOut = jest.fn();
  onSignedOut(signedOut);
  global.fetch = jest.fn(async () => response(401, { detail: 'Sign in to continue.' })) as unknown as typeof fetch;
  await expect(getJson('/api/flashcards')).rejects.toBeInstanceOf(ApiError);
  (session.accessToken as jest.Mock).mockResolvedValue(null);
  await expect(getJson('/api/flashcards')).rejects.toThrow('Sign in to continue.');
  expect(signedOut).toHaveBeenCalledTimes(2);
});

test('a 402 explains the shortfall in plain words', async () => {
  global.fetch = jest.fn(async () => response(402, { detail: 'Not enough credits for this action.', balance_credits: 2, required_credits: 13, top_up_url: '' })) as unknown as typeof fetch;
  await expect(postJson('/api/quiz/generate', { topic: 'x' })).rejects.toThrow('You have 2 credits and this needs about 13.');
});

function streamingResponse(chunks: string[], failAfter?: number) {
  let i = 0;
  const encoder = new TextEncoder();
  return { ok: true, status: 200, body: { getReader: () => ({ read: async () => {
    if (failAfter !== undefined && i === failAfter) throw new TypeError('Network request failed');
    return i < chunks.length ? { done: false, value: encoder.encode(chunks[i++]) } : { done: true, value: undefined };
  } }) } };
}

test('a streamed answer arrives token by token', async () => {
  global.fetch = jest.fn(async () => streamingResponse(['data: {"type":"token","text":"F = "}\n\n', 'data: {"type":"token","text":"ma"}\n\ndata: {"type":"done"}\n\n'])) as unknown as typeof fetch;
  const events: unknown[] = [];
  await stream('/api/chat/stream', { question: 'q' }, e => events.push(e));
  expect(events).toEqual([{ type: 'token', text: 'F = ' }, { type: 'token', text: 'ma' }, { type: 'done' }]);
});

test('a dropped connection mid-stream is a clear error after the partial answer', async () => {
  global.fetch = jest.fn(async () => streamingResponse(['data: {"type":"token","text":"Partial"}\n\n', 'never'], 1)) as unknown as typeof fetch;
  const events: unknown[] = [];
  await expect(stream('/api/chat/stream', { question: 'q' }, e => events.push(e))).rejects.toThrow('The connection dropped');
  expect(events).toEqual([{ type: 'token', text: 'Partial' }]);
});
