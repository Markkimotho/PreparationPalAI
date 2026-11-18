/**
 * The learner's profile for the whole web app. Loaded once after access is granted; saving is
 * optimistic with rollback. If the profile cannot be loaded (an older server, a network error),
 * the app opens with defaults instead of blocking, and setup is not forced.
 */
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import { DEFAULT_PROFILE, getProfile, getWorkspace, putProfile, type Profile } from '../api/profile';

type Status = 'loading' | 'ready' | 'unavailable';
interface ProfileValue { profile: Profile; status: Status; workspace: string; save: (changes: Partial<Profile>) => Promise<void> }

const ProfileContext = createContext<ProfileValue | null>(null);

export function ProfileProvider({ children }: { children: ReactNode }) {
  const [profile, setProfile] = useState<Profile>(DEFAULT_PROFILE);
  const [status, setStatus] = useState<Status>('loading');
  const [workspace, setWorkspace] = useState('');

  useEffect(() => {
    let live = true;
    Promise.all([getProfile(), getWorkspace()])
      .then(([p, w]) => { if (live) { setProfile(p); setWorkspace(w); setStatus('ready'); } })
      .catch(() => { if (live) setStatus('unavailable'); });
    return () => { live = false; };
  }, []);

  const save = useCallback(async (changes: Partial<Profile>) => {
    const before = profile;
    const next = { ...profile, ...changes };
    setProfile(next);
    try {
      setProfile(await putProfile(next));
    } catch (e) {
      setProfile(before);
      throw e;
    }
  }, [profile]);

  const value = useMemo(() => ({ profile, status, workspace, save }), [profile, status, workspace, save]);
  return <ProfileContext.Provider value={value}>{children}</ProfileContext.Provider>;
}

const FALLBACK: ProfileValue = { profile: DEFAULT_PROFILE, status: 'unavailable', workspace: '', save: async () => { throw new Error('Profile unavailable.'); } };

export function useProfile(): ProfileValue {
  return useContext(ProfileContext) ?? FALLBACK;
}
