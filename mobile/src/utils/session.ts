/**
 * Sign-in for the phone apps: standard OIDC authorization code + PKCE against Logto, through the
 * system browser. Tokens live only in the device keychain (expo-secure-store). The access token is
 * for our API resource; a refresh token keeps the learner signed in.
 */
import * as AuthSession from 'expo-auth-session';
import * as SecureStore from 'expo-secure-store';

import { API_URL, APP_SCHEME } from '@/constants/config';

interface NativeConfig { endpoint: string; client_id: string; resource: string }
interface Stored { accessToken: string; refreshToken?: string; expiresAt: number }

const KEY = 'preparationpal.tokens';
const EARLY = 60_000;              // refresh a minute before expiry
let config: NativeConfig | null = null;
let discovery: AuthSession.DiscoveryDocument | null = null;

export function resetForTests() { config = null; discovery = null; }

async function setup(): Promise<{ config: NativeConfig; discovery: AuthSession.DiscoveryDocument }> {
  if (!config) {
    const response = await fetch(`${API_URL}/api/auth/status`);
    const status = await response.json();
    if (status.mode !== 'oidc' || !status.native?.client_id) throw new Error('Sign-in is not set up on this server yet.');
    config = status.native as NativeConfig;
  }
  discovery ??= await AuthSession.fetchDiscoveryAsync(`${config.endpoint}/oidc`);
  return { config, discovery };
}

async function save(tokens: { accessToken: string; refreshToken?: string; expiresIn?: number }, previousRefresh?: string) {
  const stored: Stored = { accessToken: tokens.accessToken, refreshToken: tokens.refreshToken ?? previousRefresh,
    expiresAt: Date.now() + (tokens.expiresIn ?? 3600) * 1000 };
  await SecureStore.setItemAsync(KEY, JSON.stringify(stored));
}

async function load(): Promise<Stored | null> {
  const raw = await SecureStore.getItemAsync(KEY);
  try { return raw ? (JSON.parse(raw) as Stored) : null; } catch { return null; }
}

export const redirectUri = () => AuthSession.makeRedirectUri({ scheme: APP_SCHEME, path: 'auth/callback' });

/** Opens the sign-in page. Resolves true when signed in, false if the learner cancelled. */
export async function signIn(): Promise<boolean> {
  const { config: c, discovery: d } = await setup();
  const request = new AuthSession.AuthRequest({
    clientId: c.client_id, redirectUri: redirectUri(), usePKCE: true, prompt: AuthSession.Prompt.Consent,
    scopes: ['openid', 'offline_access', 'profile', 'email', 'roles'], extraParams: { resource: c.resource },
  });
  const result = await request.promptAsync(d);
  if (result.type !== 'success') return false;
  const tokens = await AuthSession.exchangeCodeAsync({
    clientId: c.client_id, code: result.params.code, redirectUri: redirectUri(),
    extraParams: { code_verifier: request.codeVerifier ?? '', resource: c.resource },
  }, d);
  await save(tokens);
  return true;
}

/** A valid access token, refreshed if needed, or null when the learner must sign in again. */
export async function accessToken(): Promise<string | null> {
  const stored = await load();
  if (!stored) return null;
  if (stored.expiresAt - EARLY > Date.now()) return stored.accessToken;
  if (!stored.refreshToken) { await SecureStore.deleteItemAsync(KEY); return null; }
  try {
    const { config: c, discovery: d } = await setup();
    const fresh = await AuthSession.refreshAsync({ clientId: c.client_id, refreshToken: stored.refreshToken, extraParams: { resource: c.resource } }, d);
    await save(fresh, stored.refreshToken);
    return fresh.accessToken;
  } catch {
    await SecureStore.deleteItemAsync(KEY);
    return null;
  }
}

export async function signOut(): Promise<void> {
  const stored = await load();
  try {
    if (stored?.refreshToken) {
      const { config: c, discovery: d } = await setup();
      await AuthSession.revokeAsync({ token: stored.refreshToken, clientId: c.client_id }, d);
    }
  } catch {
    /* offline or already revoked: still sign out locally */
  } finally {
    await SecureStore.deleteItemAsync(KEY);
  }
}
