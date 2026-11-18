import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';

import { onSignedOut } from '@/utils/api';
import { clearCache } from '@/utils/cache';
import { endPurchases } from '@/utils/purchases';
import * as session from '@/utils/session';

type State = 'loading' | 'signed-out' | 'signed-in';
interface SessionValue { state: State; notice: string; signIn: () => Promise<void>; signOut: () => Promise<void>; error: string }

const SessionContext = createContext<SessionValue | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<State>('loading');
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    onSignedOut(() => { setNotice('Your session ended. Sign in again to continue.'); setState('signed-out'); });
    session.accessToken().then(token => setState(token ? 'signed-in' : 'signed-out')).catch(() => setState('signed-out'));
    return () => onSignedOut(null);
  }, []);

  const signIn = useCallback(async () => {
    setError('');
    try {
      if (await session.signIn()) { setNotice(''); setState('signed-in'); }
    } catch (e) {
      setError((e as Error).message || 'Could not reach the sign-in page. Please retry.');
    }
  }, []);

  const signOut = useCallback(async () => {
    await endPurchases();
    await session.signOut();
    await clearCache();                    // a shared phone must not keep the last learner's cards
    setNotice('');
    setState('signed-out');
  }, []);

  const value = useMemo(() => ({ state, notice, error, signIn, signOut }), [state, notice, error, signIn, signOut]);
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionValue {
  const value = useContext(SessionContext);
  if (!value) throw new Error('useSession must be used inside SessionProvider');
  return value;
}
