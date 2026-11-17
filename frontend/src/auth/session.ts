/**
 * Sign-in for hosted deployments. The only file that knows the provider is Logto: swap it here.
 * The app asks for an access token for our API resource only; the server verifies it.
 */
import LogtoClient from '@logto/browser';

export interface WebAuthConfig { endpoint: string; client_id: string; resource: string }

let client: LogtoClient | null = null;
let resource = '';

export function configureSession(config: WebAuthConfig) {
  resource = config.resource;
  client = new LogtoClient({ endpoint: config.endpoint, appId: config.client_id, resources: [config.resource], scopes: ['email', 'roles'] });
}

export function resetSessionForTests() { client = null; resource = ''; }

function required(): LogtoClient {
  if (!client) throw new Error('Sign-in is not configured');
  return client;
}

export const session = {
  isSignedIn: () => required().isAuthenticated(),
  signIn: async () => required().signIn(`${window.location.origin}/auth/callback`),
  handleCallback: (url: string) => required().handleSignInCallback(url),
  /** A fresh access token, or null when the session can no longer be refreshed (treat as signed out). */
  token: async (): Promise<string | null> => {
    try { return await required().getAccessToken(resource); } catch { return null; }
  },
  signOut: async () => required().signOut(window.location.origin),
};
