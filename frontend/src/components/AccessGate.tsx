import { useEffect, useState, type ReactNode } from 'react';
import { apiFetch, setAccessKey, setTokenProvider, setUnauthorizedHandler } from '../api/access';
import { configureSession, session, type WebAuthConfig } from '../auth/session';

type State = 'loading' | 'locked' | 'signin' | 'open';
interface Status { enabled: boolean; mode?: 'tokens' | 'oidc'; web?: WebAuthConfig }

export function AccessGate({ children }: { children: ReactNode }) {
  const [state, setState] = useState<State>('loading');
  const [key, setKey] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const r = await fetch('/api/auth/status');
      if (!r.ok) throw new Error('Could not check workspace access. Reload to retry.');
      const status: Status = await r.json();
      if (!status.enabled) return setState('open');
      if (status.mode !== 'oidc') return setState('locked');
      if (!status.web?.client_id) {
        setError('Sign-in is not set up yet. Ask the administrator to finish the sign-in configuration.');
        return setState('signin');
      }
      configureSession(status.web);
      setUnauthorizedHandler(() => {
        setTokenProvider(null);
        setNotice('Your session ended. Sign in again to continue.');
        setState('signin');
      });
      if (window.location.pathname === '/auth/callback') {
        try {
          await session.handleCallback(window.location.href);
        } catch {
          setError('Sign-in did not complete. Please try again.');
        }
        window.history.replaceState(null, '', '/prepare');       // drop the one-time code from the address bar
      }
      if (cancelled) return;
      if (await session.isSignedIn()) {
        setTokenProvider(session.token);
        setState('open');
      } else {
        setState('signin');
      }
    })().catch(e => { setError((e as Error).message); setState('locked'); });
    return () => { cancelled = true; };
  }, []);

  if (state === 'open') return <>{children}</>;

  if (state === 'signin') {
    return <main className="access-page"><section className="access-card access-welcome">
      <div className="access-brand"><span className="access-logo" aria-hidden />PreparationPalAI</div>
      <h1>Study deeply.<br />Prepare confidently.</h1>
      <p>Sign in to keep your notes, decks and progress in one place, on the web and on your phone.</p>
      <ul className="access-promises" aria-label="What you get">
        <li data-tone="blue"><span aria-hidden>✦</span>Answers from your own notes, with sources</li>
        <li data-tone="amber"><span aria-hidden>✦</span>Flashcards and quizzes that explain</li>
        <li data-tone="green"><span aria-hidden>✦</span>Exam and interview practice with a coach</li>
        <li data-tone="coral"><span aria-hidden>✦</span>500 free credits when you confirm your email</li>
      </ul>
      {notice && <p role="status">{notice}</p>}
      <button type="button" disabled={busy || !!error && error.startsWith('Sign-in is not set up')}
        onClick={async () => { setBusy(true); try { await session.signIn(); } catch { setError('Could not reach the sign-in page. Please retry.'); setBusy(false); } }}>
        {busy ? 'Opening sign-in…' : 'Sign in or create an account'}
      </button>
      {error && <p role="alert">{error}</p>}
    </section></main>;
  }

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
