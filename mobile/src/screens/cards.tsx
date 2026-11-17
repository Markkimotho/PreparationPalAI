import { Link } from 'expo-router';
import { useCallback, useEffect, useState } from 'react';

import { Body, Button, Card, Field, Heading, Notice, Screen } from '@/components/ui';
import { getJson, postJson } from '@/utils/api';
import { cached } from '@/utils/cache';

export interface DeckSummary { id: string; name: string; card_count: number }
export interface Deck { id: string; name: string; cards: { id: string; front: string; back: string }[] }

export function Cards() {
  const [decks, setDecks] = useState<DeckSummary[]>([]);
  const [offline, setOffline] = useState(false);
  const [topic, setTopic] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    try {
      const result = await cached('decks', () => getJson<{ decks: DeckSummary[] }>('/api/flashcards'));
      setDecks(result.value?.decks ?? []); setOffline(result.offline);
    } catch (e) {
      setError((e as Error).message);
    }
  }, []);
  useEffect(() => { void load(); }, [load]);

  const generate = async () => {
    setBusy(true); setError('');
    try {
      await postJson<Deck>('/api/flashcards/generate', { topic: topic.trim(), n: 10 });
      setTopic('');
      await load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return <Screen>
    <Heading>Flashcards</Heading>
    {offline && <Notice text="You're offline. Showing the cards saved on this phone." />}
    <Field label="Make a deck from your notes about…" value={topic} onChangeText={setTopic} placeholder="Cell biology" />
    <Button label="Make 10 cards" busy={busy} disabled={!topic.trim() || offline} onPress={() => void generate()} />
    <Notice text={error} kind="error" />
    {decks.length === 0 && !error && <Body muted>No decks yet.</Body>}
    {decks.map(d => <Link key={d.id} href={{ pathname: '/deck/[id]', params: { id: d.id } }} asChild>
      <Card><Heading level={2}>{d.name}</Heading><Body muted>{`${d.card_count} cards`}</Body></Card>
    </Link>)}
  </Screen>;
}
