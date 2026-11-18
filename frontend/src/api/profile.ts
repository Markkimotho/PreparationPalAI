// The signed-in learner's profile (GET/PUT /api/profile): identity, look, and what the tutor tailors to.
import { apiFetch } from './access';

export type Accent = 'blue' | 'amber' | 'green' | 'coral';
export interface Profile {
  display_name: string; avatar_seed: string; accent: Accent; goal: 'exam' | 'interview' | 'understand';
  subjects: string[]; level: 'beginner' | 'intermediate' | 'advanced'; exam_context: string; language: string;
  daily_goal: number; onboarded: boolean;
}

export const DEFAULT_PROFILE: Profile = {
  display_name: '', avatar_seed: '', accent: 'blue', goal: 'understand', subjects: [], level: 'intermediate',
  exam_context: '', language: 'English', daily_goal: 10, onboarded: false,
};

/** Only the fields the server accepts (it refuses unknown ones, e.g. updated_at). */
export function only(raw: Record<string, unknown>): Profile {
  return Object.fromEntries(Object.keys(DEFAULT_PROFILE).map(k => [k, raw[k] ?? DEFAULT_PROFILE[k as keyof Profile]])) as unknown as Profile;
}

async function json<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let detail = 'Could not save your profile. Please retry.';
    try {
      const body = await response.json();
      if (typeof body.detail === 'string') detail = body.detail;
    } catch { /* keep the generic message */ }
    throw Object.assign(new Error(detail), { status: response.status });
  }
  return response.json() as Promise<T>;
}

export async function getProfile(): Promise<Profile> {
  return only(await json<Record<string, unknown>>(await apiFetch('/api/profile')));
}

export async function putProfile(profile: Profile): Promise<Profile> {
  return only(await json<Record<string, unknown>>(await apiFetch('/api/profile', {
    method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(only(profile as unknown as Record<string, unknown>)),
  })));
}

export async function getWorkspace(): Promise<string> {
  return (await json<{ workspace: string }>(await apiFetch('/api/auth/me'))).workspace;
}

/** Text-safe accent colours for the web's light surfaces (each passes 4.5:1 on white). */
export const ACCENT_COLOURS: Record<Accent, { main: string; soft: string; deep: string }> = {
  blue: { main: '#1d5fc4', soft: '#e3edff', deep: '#163f80' },
  amber: { main: '#a35a04', soft: '#fff1d6', deep: '#7a4303' },
  green: { main: '#14775a', soft: '#dbf4e8', deep: '#0f523e' },
  coral: { main: '#b83a2a', soft: '#ffe6e1', deep: '#8a2b1f' },
};
