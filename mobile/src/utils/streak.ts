/**
 * A daily study streak, kept on the phone. Any study action (a question, a quiz answer, a card,
 * a practice answer) marks today. The streak is the run of consecutive days ending today, or
 * yesterday if the learner has not studied yet today (so the streak is not lost at midnight).
 * Stored under `cache:` so signing out clears it with the rest of the learner's local data.
 */
import AsyncStorage from '@react-native-async-storage/async-storage';

const KEY = 'cache:streak-days';
const KEEP = 120;

/** The local calendar day, YYYY-MM-DD (not UTC: a learner in Nairobi studying at 1am is on today). */
export function dayOf(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

function previous(day: string): string {
  const [y, m, d] = day.split('-').map(Number);
  return dayOf(new Date(y, m - 1, d - 1));
}

export function streakLength(days: readonly string[], today: Date): number {
  const studied = new Set(days);
  let day = dayOf(today);
  if (!studied.has(day)) day = previous(day);
  let length = 0;
  while (studied.has(day)) { length += 1; day = previous(day); }
  return length;
}

async function load(): Promise<string[]> {
  try {
    const raw = JSON.parse((await AsyncStorage.getItem(KEY)) ?? '[]');
    return Array.isArray(raw) ? raw.filter((d): d is string => typeof d === 'string') : [];
  } catch {
    return [];
  }
}

export async function currentStreak(now = new Date()): Promise<{ days: number; studiedToday: boolean }> {
  const days = await load();
  return { days: streakLength(days, now), studiedToday: days.includes(dayOf(now)) };
}

/** Mark today as a study day. Returns the streak after marking. */
export async function recordStudy(now = new Date()): Promise<number> {
  const days = await load();
  const today = dayOf(now);
  if (!days.includes(today)) {
    days.push(today);
    days.sort();
    await AsyncStorage.setItem(KEY, JSON.stringify(days.slice(-KEEP)));
  }
  return streakLength(days, now);
}
