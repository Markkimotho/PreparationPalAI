/**
 * The signed-in learner's profile (server: /api/profile), shared with every screen.
 *
 * Loaded once after sign-in and cached on the phone (`cache:profile`, cleared on sign-out) so the
 * app opens personalised offline. Saving is optimistic: the app changes at once and rolls back if
 * the server refuses. If the profile cannot be loaded at all (offline, first launch), the learner
 * still gets the app with defaults; setup is offered again next time.
 */
import AsyncStorage from '@react-native-async-storage/async-storage';
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';

import type { Accent } from '@/constants/theme';
import { getJson, putJson } from '@/utils/api';

export interface Profile {
  display_name: string; avatar_seed: string; accent: Accent; goal: 'exam' | 'interview' | 'understand';
  subjects: string[]; level: 'beginner' | 'intermediate' | 'advanced'; exam_context: string; language: string;
  daily_goal: number; onboarded: boolean;
}

export const DEFAULT_PROFILE: Profile = {
  display_name: '', avatar_seed: '', accent: 'blue', goal: 'understand', subjects: [], level: 'intermediate',
  exam_context: '', language: 'English', daily_goal: 10, onboarded: false,
};
const CACHE = 'cache:profile';

type Status = 'loading' | 'ready' | 'unavailable';
interface ProfileValue {
  profile: Profile; status: Status; workspace: string;
  /** Save changes; resolves when the server has them, rejects (and rolls back) if it refused. */
  save: (changes: Partial<Profile>) => Promise<void>;
}

const ProfileContext = createContext<ProfileValue | null>(null);

function only(raw: Record<string, unknown>): Profile {
  return Object.fromEntries(Object.keys(DEFAULT_PROFILE).map(k => [k, raw[k] ?? DEFAULT_PROFILE[k as keyof Profile]])) as unknown as Profile;
}

export function ProfileProvider({ children }: { children: ReactNode }) {
  const [profile, setProfile] = useState<Profile>(DEFAULT_PROFILE);
  const [status, setStatus] = useState<Status>('loading');
  const [workspace, setWorkspace] = useState('');

  useEffect(() => {
    let live = true;
    (async () => {
      const cachedRaw = await AsyncStorage.getItem(CACHE).catch(() => null);
      if (cachedRaw && live) { try { setProfile(only(JSON.parse(cachedRaw))); setStatus('ready'); } catch { /* ignore a damaged cache */ } }
      try {
        const [fresh, me] = await Promise.all([getJson<Record<string, unknown>>('/api/profile'), getJson<{ workspace: string }>('/api/auth/me')]);
        if (!live) return;
        setProfile(only(fresh)); setWorkspace(me.workspace); setStatus('ready');
        await AsyncStorage.setItem(CACHE, JSON.stringify(only(fresh))).catch(() => undefined);
      } catch {
        if (live && !cachedRaw) setStatus('unavailable');
      }
    })();
    return () => { live = false; };
  }, []);

  const save = useCallback(async (changes: Partial<Profile>) => {
    const before = profile;
    const next = { ...profile, ...changes };
    setProfile(next);
    try {
      const stored = await putJson<Record<string, unknown>>('/api/profile', next);
      const clean = only(stored);
      setProfile(clean);
      await AsyncStorage.setItem(CACHE, JSON.stringify(clean)).catch(() => undefined);
    } catch (e) {
      setProfile(before);
      throw e;
    }
  }, [profile]);

  const value = useMemo(() => ({ profile, status, workspace, save }), [profile, status, workspace, save]);
  return <ProfileContext.Provider value={value}>{children}</ProfileContext.Provider>;
}

const SIGNED_OUT: ProfileValue = {
  profile: DEFAULT_PROFILE, status: 'unavailable', workspace: '',
  save: async () => { throw new Error('Sign in to save your profile.'); },
};

/** The profile, or defaults outside a signed-in session (signed-out screens, isolated tests). */
export function useProfile(): ProfileValue {
  return useContext(ProfileContext) ?? SIGNED_OUT;
}

/** The learner's own accent colour, or blue outside a signed-in session. */
export function useAccent(): Accent {
  return useContext(ProfileContext)?.profile.accent ?? 'blue';
}
