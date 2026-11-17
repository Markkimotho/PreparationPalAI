/** Every API call goes through here: the access token is attached, a 401 sends the learner to sign-in. */
import { fetch as streamingFetch } from 'expo/fetch';

import { API_URL } from '@/constants/config';
import { accessToken } from './session';
import { createSseParser } from './sse';

export class ApiError extends Error {
  constructor(message: string, readonly status: number) { super(message); }
}

let signedOutListener: (() => void) | null = null;
export function onSignedOut(listener: (() => void) | null) { signedOutListener = listener; }

function creditsMessage(body: { detail?: string; balance_credits?: number; required_credits?: number }) {
  const parts = [body.detail ?? 'Not enough credits for this action.'];
  if (typeof body.balance_credits === 'number' && typeof body.required_credits === 'number') {
    parts.push(`You have ${body.balance_credits} credits and this needs about ${body.required_credits}.`);
  }
  return parts.join(' ');
}

async function authorised(): Promise<string> {
  const token = await accessToken();
  if (!token) { signedOutListener?.(); throw new ApiError('Sign in to continue.', 401); }
  return token;
}

async function failure(response: { status: number; statusText?: string; json: () => Promise<unknown> }): Promise<ApiError> {
  let body: Record<string, unknown> = {};
  try { body = (await response.json()) as Record<string, unknown>; } catch { /* not JSON */ }
  if (response.status === 401) signedOutListener?.();
  const message = response.status === 402 ? creditsMessage(body) : String(body.detail ?? response.statusText ?? 'Request failed');
  return new ApiError(message, response.status);
}

export async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = await authorised();
  const response = await fetch(`${API_URL}${path}`, { ...init, headers: { ...(init.headers as Record<string, string>), Authorization: `Bearer ${token}` } });
  if (!response.ok) throw await failure(response);
  return (response.status === 204 ? undefined : await response.json()) as T;
}

export const getJson = <T>(path: string) => request<T>(path);
export const postJson = <T>(path: string, body: unknown) =>
  request<T>(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
export const deleteRequest = (path: string) => request<void>(path, { method: 'DELETE' });

export type StreamEvent = { type: 'token'; text: string } | { type: 'sources'; sources: { source: string; page?: number | string }[] }
  | { type: 'tool'; name: string } | { type: 'error'; message: string } | { type: 'done' };

/** POST and read a Server-Sent Events answer as it arrives. A dropped connection rejects after the partial answer. */
export async function stream(path: string, body: unknown, onEvent: (event: StreamEvent) => void, signal?: AbortSignal): Promise<void> {
  const token = await authorised();
  const response = await streamingFetch(`${API_URL}${path}`, {
    method: 'POST', signal, body: JSON.stringify(body),
    headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream', Authorization: `Bearer ${token}` },
  });
  if (!response.ok) throw await failure(response as unknown as Response);
  const reader = response.body!.getReader();
  const decoder = new TextDecoder();
  const push = createSseParser(frame => onEvent(frame as StreamEvent));
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      push(decoder.decode(value, { stream: true }));
    }
  } catch (error) {
    if ((error as Error).name === 'AbortError') throw error;
    throw new ApiError('The connection dropped before the answer finished. Check your connection and try again.', 0);
  }
}
