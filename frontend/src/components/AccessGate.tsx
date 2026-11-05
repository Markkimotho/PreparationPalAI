import { useEffect, useState, type ReactNode } from 'react';
import { apiFetch, setAccessKey } from '../api/access';

export function AccessGate({ children }: { children: ReactNode }) {
  const [state, setState] = useState<'loading' | 'locked' | 'open'>('loading');
  const [key, setKey] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    fetch('/api/auth/status').then(async r => {
      if (!r.ok) throw new Error('Could not check workspace access. Reload to retry.');
      setState((await r.json()).enabled ? 'locked' : 'open');
    }).catch(e => { setError(e.message); setState('locked'); });
  }, []);
  if (state === 'open') return <>{children}</>;
  return <main className="access-page"><form className="access-card" onSubmit={async e => {
    e.preventDefault(); setBusy(true); setError(''); setAccessKey(key.trim());
    try {
      const r = await apiFetch('/api/auth/me');
      if (!r.ok) throw new Error('Invalid or revoked access key. Contact your workspace administrator.');
      setKey(''); setState('open');
    } catch (e) { setAccessKey(''); setError((e as Error).message); }
    finally { setBusy(false); }
  }}><h1>PreparationPalAI</h1><p>Sign in to your study workspace.</p>
    {state === 'loading' ? <p role="status">Checking access…</p> : <>
      <label htmlFor="access-key">Workspace access key</label>
      <input id="access-key" type="password" autoComplete="off" required value={key} onChange={e => setKey(e.target.value)} />
      <button disabled={busy}>{busy ? 'Signing in…' : 'Sign in'}</button>
      <p>Your key stays in this tab’s memory. Reloading signs you out.</p>
    </>}{error && <p role="alert">{error}</p>}</form></main>;
}
