const mockStore: Record<string, string> = {};
jest.mock('expo-secure-store', () => ({
  getItemAsync: jest.fn(async (k: string) => mockStore[k] ?? null),
  setItemAsync: jest.fn(async (k: string, v: string) => { mockStore[k] = v; }),
  deleteItemAsync: jest.fn(async (k: string) => { delete mockStore[k]; }),
}));
const mockAuth = {
  promptAsync: jest.fn(), exchangeCodeAsync: jest.fn(), refreshAsync: jest.fn(), revokeAsync: jest.fn(async (..._a: unknown[]) => true),
  fetchDiscoveryAsync: jest.fn(async (..._a: unknown[]) => ({ tokenEndpoint: 'https://auth.example.com/oidc/token', revocationEndpoint: 'https://auth.example.com/oidc/token/revocation', authorizationEndpoint: 'https://auth.example.com/oidc/auth' })),
  configs: [] as unknown[],
};
jest.mock('expo-auth-session', () => ({
  AuthRequest: jest.fn().mockImplementation((config: unknown) => { mockAuth.configs.push(config); return { codeVerifier: 'verifier-123', promptAsync: mockAuth.promptAsync }; }),
  exchangeCodeAsync: (...a: unknown[]) => mockAuth.exchangeCodeAsync(...a),
  refreshAsync: (...a: unknown[]) => mockAuth.refreshAsync(...a),
  revokeAsync: (...a: unknown[]) => mockAuth.revokeAsync(...a),
  fetchDiscoveryAsync: (...a: unknown[]) => mockAuth.fetchDiscoveryAsync(...a),
  makeRedirectUri: () => 'preparationpal://auth/callback',
  Prompt: { Consent: 'consent' },
}));

import * as session from './session';

const status = { enabled: true, mode: 'oidc', native: { endpoint: 'https://auth.example.com', client_id: 'native-app', resource: 'https://api.example.com' } };
const ok = (body: unknown) => ({ ok: true, status: 200, json: async () => body });

beforeEach(() => {
  for (const k of Object.keys(mockStore)) delete mockStore[k];
  jest.clearAllMocks();
  mockAuth.configs.length = 0;
  session.resetForTests();
  global.fetch = jest.fn(async () => ok(status)) as unknown as typeof fetch;
});

test('signing in uses PKCE, asks for a refresh token and an access token for our API, and keeps tokens in the keychain', async () => {
  mockAuth.promptAsync.mockResolvedValue({ type: 'success', params: { code: 'code-1' } });
  mockAuth.exchangeCodeAsync.mockResolvedValue({ accessToken: 'at-1', refreshToken: 'rt-1', expiresIn: 3600, issuedAt: Math.floor(Date.now() / 1000) });
  expect(await session.signIn()).toBe(true);
  expect(mockAuth.configs[0]).toMatchObject({ clientId: 'native-app', redirectUri: 'preparationpal://auth/callback', usePKCE: true,
    scopes: expect.arrayContaining(['openid', 'offline_access', 'email', 'roles']), extraParams: { resource: 'https://api.example.com' } });
  expect(mockAuth.exchangeCodeAsync).toHaveBeenCalledWith(expect.objectContaining({ code: 'code-1', clientId: 'native-app',
    extraParams: { code_verifier: 'verifier-123', resource: 'https://api.example.com' } }), expect.anything());
  expect(await session.accessToken()).toBe('at-1');
  expect(JSON.parse(mockStore['preparationpal.tokens']).refreshToken).toBe('rt-1');
});

test('a cancelled sign-in stores nothing', async () => {
  mockAuth.promptAsync.mockResolvedValue({ type: 'cancel' });
  expect(await session.signIn()).toBe(false);
  expect(await session.accessToken()).toBeNull();
});

test('an expired token is refreshed for our API resource', async () => {
  mockStore['preparationpal.tokens'] = JSON.stringify({ accessToken: 'old', refreshToken: 'rt-1', expiresAt: Date.now() - 1000 });
  mockAuth.refreshAsync.mockResolvedValue({ accessToken: 'new', refreshToken: 'rt-2', expiresIn: 3600 });
  expect(await session.accessToken()).toBe('new');
  expect(mockAuth.refreshAsync).toHaveBeenCalledWith({ clientId: 'native-app', refreshToken: 'rt-1', extraParams: { resource: 'https://api.example.com' } }, expect.anything());
  expect(JSON.parse(mockStore['preparationpal.tokens']).refreshToken).toBe('rt-2');
});

test('a refresh that fails signs the learner out and clears the keychain', async () => {
  mockStore['preparationpal.tokens'] = JSON.stringify({ accessToken: 'old', refreshToken: 'rt-1', expiresAt: Date.now() - 1000 });
  mockAuth.refreshAsync.mockRejectedValue(new Error('invalid_grant'));
  expect(await session.accessToken()).toBeNull();
  expect(mockStore['preparationpal.tokens']).toBeUndefined();
});

test('signing out revokes the refresh token and clears the keychain even if revocation fails', async () => {
  mockStore['preparationpal.tokens'] = JSON.stringify({ accessToken: 'at', refreshToken: 'rt-1', expiresAt: Date.now() + 3600_000 });
  mockAuth.revokeAsync.mockRejectedValue(new Error('offline'));
  await session.signOut();
  expect(mockAuth.revokeAsync).toHaveBeenCalledWith(expect.objectContaining({ token: 'rt-1', clientId: 'native-app' }), expect.anything());
  expect(mockStore['preparationpal.tokens']).toBeUndefined();
});

test('explains when the server has no native sign-in configured', async () => {
  global.fetch = jest.fn(async () => ok({ ...status, native: { ...status.native, client_id: '' } })) as unknown as typeof fetch;
  await expect(session.signIn()).rejects.toThrow('Sign-in is not set up');
});
