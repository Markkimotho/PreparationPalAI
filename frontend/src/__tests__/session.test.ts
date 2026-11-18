import { beforeEach, expect, it, vi } from 'vitest';

const calls = vi.hoisted(() => ({ ctor: [] as unknown[], signIn: vi.fn(), callback: vi.fn(), token: vi.fn(async () => 'jwt-1'),
  authed: vi.fn(async () => true), signOut: vi.fn() }));
vi.mock('@logto/browser', () => ({ default: class {
  constructor(config: unknown) { calls.ctor.push(config); }
  signIn = calls.signIn; handleSignInCallback = calls.callback; getAccessToken = calls.token;
  isAuthenticated = calls.authed; signOut = calls.signOut;
} }));

import { configureSession, session } from '../auth/session';

beforeEach(() => { calls.ctor.length = 0; vi.clearAllMocks(); });
const config = { endpoint: 'https://auth.example.com', client_id: 'web-app', resource: 'https://api.example.com' };

it('configures Logto for the API resource and the email and roles claims', () => {
  configureSession(config);
  expect(calls.ctor[0]).toEqual({ endpoint: 'https://auth.example.com', appId: 'web-app', resources: ['https://api.example.com'], scopes: ['email', 'roles'] });
});

it('signs in through the callback page and asks for an access token for our API only', async () => {
  configureSession(config);
  await session.signIn();
  expect(calls.signIn).toHaveBeenCalledWith(`${window.location.origin}/auth/callback`);
  expect(await session.token()).toBe('jwt-1');
  expect(calls.token).toHaveBeenCalledWith('https://api.example.com');
});

it('treats a token that cannot be refreshed as signed out', async () => {
  configureSession(config);
  calls.token.mockRejectedValueOnce(new Error('refresh token expired'));
  expect(await session.token()).toBeNull();
});

it('signs out back to the site', async () => {
  configureSession(config);
  await session.signOut();
  expect(calls.signOut).toHaveBeenCalledWith(window.location.origin);
});

it('refuses to sign in before it is configured', async () => {
  await expect(import('../auth/session').then(async m => { m.resetSessionForTests(); await m.session.signIn(); })).rejects.toThrow('not configured');
});
