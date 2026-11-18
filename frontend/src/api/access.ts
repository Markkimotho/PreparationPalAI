/**
 * Every API request goes through apiFetch.
 * - Self-hosted: a workspace key held in memory only (never in local or session storage).
 * - Hosted: a sign-in access token from the session, fetched fresh for each request.
 * A 401, or a token that can no longer be refreshed, tells the app the learner must sign in again.
 */
let accessKey = '';
let tokenProvider: (() => Promise<string | null>) | null = null;
let onUnauthorized: (() => void) | null = null;

export function setAccessKey(key: string) { accessKey = key; }
export function setTokenProvider(provider: (() => Promise<string | null>) | null) { tokenProvider = provider; }
export function setUnauthorizedHandler(handler: (() => void) | null) { onUnauthorized = handler; }
export function resetAccessForTests() { accessKey = ''; tokenProvider = null; onUnauthorized = null; }

const signedOut = () => new Response(JSON.stringify({ detail: 'Sign in to continue.' }),
  { status: 401, headers: { 'Content-Type': 'application/json' } });

export async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  let bearer = accessKey;
  if (!bearer && tokenProvider) {
    bearer = (await tokenProvider()) ?? '';
    if (!bearer) { onUnauthorized?.(); return signedOut(); }
  }
  if (!bearer) return fetch(path, Object.keys(init).length ? init : undefined);
  const headers = new Headers(init.headers);
  headers.set('Authorization', `Bearer ${bearer}`);
  const response = await fetch(path, { ...init, headers });
  if (response.status === 401 && tokenProvider) onUnauthorized?.();
  return response;
}
