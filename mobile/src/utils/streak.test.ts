import AsyncStorage from '@react-native-async-storage/async-storage';

import { currentStreak, dayOf, recordStudy, streakLength, todayCount } from './streak';

const at = (y: number, m: number, d: number, h = 12) => new Date(y, m - 1, d, h);
beforeEach(() => AsyncStorage.clear());

test('the day is the local calendar day, not UTC', () => {
  expect(dayOf(at(2026, 11, 18, 0))).toBe('2026-11-18');
  expect(dayOf(at(2026, 11, 18, 23))).toBe('2026-11-18');
});

test('consecutive days ending today count, a gap ends the run', () => {
  expect(streakLength(['2026-11-14', '2026-11-16', '2026-11-17', '2026-11-18'], at(2026, 11, 18))).toBe(3);
});

test('a streak survives until the learner has had all of today to study', () => {
  expect(streakLength(['2026-11-16', '2026-11-17'], at(2026, 11, 18))).toBe(2);
  expect(streakLength(['2026-11-16'], at(2026, 11, 18))).toBe(0);
});

test('runs cross month and year boundaries', () => {
  expect(streakLength(['2026-12-30', '2026-12-31', '2027-01-01'], at(2027, 1, 1))).toBe(3);
  expect(streakLength(['2026-02-28', '2026-03-01'], at(2026, 3, 1))).toBe(2);
});

test('recording is idempotent per day and persisted under the cleared-on-sign-out prefix', async () => {
  expect(await recordStudy(at(2026, 11, 17))).toBe(1);
  expect(await recordStudy(at(2026, 11, 18, 9))).toBe(2);
  expect(await recordStudy(at(2026, 11, 18, 21))).toBe(2);
  expect(await currentStreak(at(2026, 11, 18))).toEqual({ days: 2, studiedToday: true });
  expect(JSON.parse((await AsyncStorage.getItem('cache:streak-days'))!)).toEqual(['2026-11-17', '2026-11-18']);
});

test('corrupt storage reads as no streak instead of crashing', async () => {
  await AsyncStorage.setItem('cache:streak-days', '{not json');
  expect(await currentStreak(at(2026, 11, 18))).toEqual({ days: 0, studiedToday: false });
});

test('each study action counts toward today, and a new day starts from zero', async () => {
  await recordStudy(at(2026, 11, 18, 9));
  await recordStudy(at(2026, 11, 18, 10));
  await recordStudy(at(2026, 11, 18, 23));
  expect(await todayCount(at(2026, 11, 18, 23))).toBe(3);
  expect(await todayCount(at(2026, 11, 19, 8))).toBe(0);
});

test('only the last month of daily counts is kept', async () => {
  await recordStudy(at(2026, 9, 1));
  await recordStudy(at(2026, 11, 18));
  expect(Object.keys(JSON.parse((await AsyncStorage.getItem('cache:study-counts'))!))).toEqual(['2026-11-18']);
});
