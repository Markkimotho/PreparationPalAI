import AsyncStorage from '@react-native-async-storage/async-storage';

import { knownCards, masteryFor, recordAnswer } from './mastery';

beforeEach(() => AsyncStorage.clear());

test('got it adds a card, still learning takes it back out', async () => {
  await recordAnswer('d1', 'c1', true);
  await recordAnswer('d1', 'c2', true);
  await recordAnswer('d1', 'c1', false);
  expect([...(await knownCards('d1'))]).toEqual(['c2']);
});

test('answering the same card twice counts once', async () => {
  await recordAnswer('d1', 'c1', true);
  await recordAnswer('d1', 'c1', true);
  expect((await knownCards('d1')).size).toBe(1);
});

test('mastery per deck is capped at the deck size and survives corrupt storage', async () => {
  await AsyncStorage.setItem('cache:mastery:d1', JSON.stringify(['a', 'b', 'c']));
  await AsyncStorage.setItem('cache:mastery:d2', '{oops');
  expect(await masteryFor([{ id: 'd1', card_count: 2 }, { id: 'd2', card_count: 5 }, { id: 'd3', card_count: 4 }]))
    .toEqual({ d1: 2, d2: 0, d3: 0 });
});

test('stored under the prefix that sign-out clears', async () => {
  await recordAnswer('d9', 'c1', true);
  expect(await AsyncStorage.getItem('cache:mastery:d9')).toBe('["c1"]');
});
