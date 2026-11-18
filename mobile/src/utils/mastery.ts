/**
 * Which cards a learner has marked "Got it", per deck, kept on the phone. "Still learning"
 * removes a card from the known set, so mastery always reflects the latest answer.
 * Stored under `cache:` so signing out clears it with the rest of the learner's local data.
 */
import AsyncStorage from '@react-native-async-storage/async-storage';

const key = (deckId: string) => `cache:mastery:${deckId}`;

async function read(deckId: string): Promise<Set<string>> {
  try {
    const raw = JSON.parse((await AsyncStorage.getItem(key(deckId))) ?? '[]');
    return new Set(Array.isArray(raw) ? raw.filter((x): x is string => typeof x === 'string') : []);
  } catch {
    return new Set();
  }
}

export async function knownCards(deckId: string): Promise<Set<string>> {
  return read(deckId);
}

export async function recordAnswer(deckId: string, cardId: string, known: boolean): Promise<void> {
  const ids = await read(deckId);
  if (known) ids.add(cardId); else ids.delete(cardId);
  await AsyncStorage.setItem(key(deckId), JSON.stringify([...ids]));
}

/** Mastered cards per deck, capped at the deck's size (cards may have been deleted since). */
export async function masteryFor(decks: readonly { id: string; card_count: number }[]): Promise<Record<string, number>> {
  const pairs = await AsyncStorage.multiGet(decks.map(d => key(d.id)));
  const result: Record<string, number> = {};
  decks.forEach((d, i) => {
    let count = 0;
    try { const raw = JSON.parse(pairs[i][1] ?? '[]'); count = Array.isArray(raw) ? raw.length : 0; } catch { count = 0; }
    result[d.id] = Math.min(count, d.card_count);
  });
  return result;
}
