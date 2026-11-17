import { useEffect, useState } from 'react';

import { Body, Button, Card, Heading, Notice, Screen } from '@/components/ui';
import { getJson } from '@/utils/api';
import { cached } from '@/utils/cache';
import type { Deck } from './cards';

export function DeckStudy({ id }: { id: string }) {
  const [deck, setDeck] = useState<Deck | null>(null);
  const [offline, setOffline] = useState(false);
  const [index, setIndex] = useState(0);
  const [flipped, setFlipped] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    cached(`deck:${id}`, () => getJson<Deck>(`/api/flashcards/${encodeURIComponent(id)}`))
      .then(r => { setDeck(r.value); setOffline(r.offline); })
      .catch(e => setError((e as Error).message));
  }, [id]);

  if (error) return <Screen><Notice text={error} kind="error" /></Screen>;
  if (!deck) return <Screen><Body muted>Loading…</Body></Screen>;
  if (deck.cards.length === 0) return <Screen><Heading>{deck.name}</Heading><Body muted>This deck has no cards yet.</Body></Screen>;
  const card = deck.cards[index];
  const move = (step: number) => { setFlipped(false); setIndex(i => (i + step + deck.cards.length) % deck.cards.length); };

  return <Screen>
    <Heading>{deck.name}</Heading>
    {offline && <Notice text="Offline: studying the copy saved on this phone." />}
    <Body muted>{`Card ${index + 1} of ${deck.cards.length}`}</Body>
    <Card><Heading level={2}>{flipped ? card.back : card.front}</Heading></Card>
    <Button label={flipped ? 'Show question' : 'Show answer'} onPress={() => setFlipped(f => !f)} />
    <Button label="Previous" variant="secondary" onPress={() => move(-1)} />
    <Button label="Next" variant="secondary" onPress={() => move(1)} />
  </Screen>;
}
