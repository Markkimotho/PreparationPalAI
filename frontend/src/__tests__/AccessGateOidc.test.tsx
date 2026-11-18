import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';

const auth = vi.hoisted(() => ({ signedIn: false, token: 'jwt-alice' as string | null, signIn: vi.fn(), callback: vi.fn(), configure: vi.fn() }));
vi.mock('../auth/session', () => ({
  configureSession: auth.configure,
  session: { isSignedIn: async () => auth.signedIn, signIn: auth.signIn, handleCallback: async () => { auth.callback(); auth.signedIn = true; },
             token: async () => auth.token, signOut: vi.fn() },
}));

import { AccessGate } from '../components/AccessGate';
import { apiFetch, resetAccessForTests } from '../api/access';

const status = { enabled: true, mode: 'oidc', issuer: 'https://auth.example.com/oidc',
  web: { endpoint: 'https://auth.example.com', client_id: 'web-app', resource: 'https://api.example.com' } };

function server(handler: (path: string) => Response) {
  const fetchMock = vi.fn(async (path: string) => handler(path));
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

beforeEach(() => { auth.signedIn = false; auth.token = 'jwt-alice'; vi.clearAllMocks(); window.history.replaceState(null, '', '/'); });
afterEach(() => { resetAccessForTests(); vi.unstubAllGlobals(); });

it('offers sign-in when nobody is signed in and starts it on click', async () => {
  server(() => json(status));
  render(<AccessGate><div>Private study</div></AccessGate>);
  await userEvent.click(await screen.findByRole('button', { name: 'Sign in or create an account' }));
  expect(auth.configure).toHaveBeenCalledWith(status.web);
  expect(auth.signIn).toHaveBeenCalled();
  expect(screen.queryByText('Private study')).not.toBeInTheDocument();
});

it('opens the app for a signed-in learner and sends their token with every request', async () => {
  auth.signedIn = true;
  const fetchMock = server(path => path.endsWith('/status') ? json(status) : json({ ok: true }));
  render(<AccessGate><div>Private study</div></AccessGate>);
  expect(await screen.findByText('Private study')).toBeInTheDocument();
  await apiFetch('/api/flashcards');
  const [, init] = fetchMock.mock.calls[fetchMock.mock.calls.length - 1] as unknown as [string, RequestInit];
  expect(new Headers(init.headers).get('Authorization')).toBe('Bearer jwt-alice');
});

it('finishes the sign-in on the callback page and returns to the app', async () => {
  window.history.replaceState(null, '', '/auth/callback?code=abc&state=xyz');
  server(() => json(status));
  render(<AccessGate><div>Private study</div></AccessGate>);
  expect(await screen.findByText('Private study')).toBeInTheDocument();
  expect(auth.callback).toHaveBeenCalled();
  expect(window.location.pathname).toBe('/prepare');
  expect(window.location.search).toBe('');                         // the one-time code does not linger in the address bar
});

it('returns to the sign-in screen when the session expires mid-use', async () => {
  auth.signedIn = true;
  server(path => path.endsWith('/status') ? json(status) : json({ detail: 'Sign in to continue.' }, 401));
  render(<AccessGate><div>Private study</div></AccessGate>);
  await screen.findByText('Private study');
  await apiFetch('/api/flashcards');
  expect(await screen.findByRole('button', { name: 'Sign in or create an account' })).toBeInTheDocument();
  expect(screen.getByRole('status')).toHaveTextContent('Your session ended. Sign in again to continue.');
});

it('treats a token that can no longer be refreshed as signed out', async () => {
  auth.signedIn = true;
  auth.token = null;
  server(path => path.endsWith('/status') ? json(status) : json({}));
  render(<AccessGate><div>Private study</div></AccessGate>);
  await screen.findByText('Private study');
  await apiFetch('/api/flashcards');
  expect(await screen.findByRole('button', { name: 'Sign in or create an account' })).toBeInTheDocument();
});

it('explains when the sign-in service is not configured instead of looping', async () => {
  server(() => json({ ...status, web: { ...status.web, client_id: '' } }));
  render(<AccessGate><div>Private study</div></AccessGate>);
  expect(await screen.findByRole('alert')).toHaveTextContent('Sign-in is not set up yet');
});
