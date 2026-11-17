import { LinearGradient } from 'expo-linear-gradient';
import { Link } from 'expo-router';
import { useCallback, useEffect, useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { Body, Button, Card, Field, Icon, Notice, PressableScale, Screen } from '@/components/ui';
import { accentColors, Fonts, Radius, type Accent } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import { getJson, postJson } from '@/utils/api';
import { cached } from '@/utils/cache';

export interface DeckSummary { id: string; name: string; card_count: number }
export interface Deck { id: string; name: string; cards: { id: string; front: string; back: string }[] }

const COVERS: Accent[] = ['green', 'blue', 'amber', 'coral'];

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

  return <Screen title="Flashcards" subtitle="Flip, swipe, remember." accent="green">
    {offline && <Notice text="You're offline. Showing the cards saved on this phone." />}
    <Card>
      <Field label="Make a deck from your notes about…" accent="green" value={topic} onChangeText={setTopic} placeholder="Cell biology" />
      <Button label="Make 10 cards" accent="green" icon={{ ios: 'rectangle.stack.badge.plus', android: 'library_add' }}
        busy={busy} disabled={!topic.trim() || offline} onPress={() => void generate()} />
    </Card>
    <Notice text={error} kind="error" />
    {decks.length === 0 && !error && <EmptyDecks />}
    <View style={styles.grid}>
      {decks.map((d, i) => <Link key={d.id} href={{ pathname: '/deck/[id]', params: { id: d.id } }} asChild>
        <DeckTile deck={d} accent={COVERS[i % COVERS.length]} />
      </Link>)}
    </View>
  </Screen>;
}

function DeckTile({ deck, accent, onPress }: { deck: DeckSummary; accent: Accent; onPress?: () => void }) {
  const colors = useTheme();
  const { main, deep } = accentColors(colors, accent);
  return <View style={styles.tileSlot}>
    <PressableScale onPress={onPress} accessibilityRole="link" accessibilityLabel={`${deck.name}, ${deck.card_count} cards`}
      style={[styles.tile, { backgroundColor: colors.surface, borderColor: colors.border, shadowColor: colors.shadow }]}>
      <LinearGradient colors={[main, deep]} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={styles.cover}>
        <View style={[styles.stack, styles.stackBack]} />
        <View style={[styles.stack, styles.stackMid]} />
        <View style={[styles.stack, styles.stackFront]}><Icon name={{ ios: 'questionmark', android: 'help' }} size={16} color={deep} /></View>
      </LinearGradient>
      <View style={styles.tileText}>
        <Text numberOfLines={2} style={[styles.deckName, { color: colors.text }]}>{deck.name}</Text>
        <Text style={[styles.deckCount, { color: colors.textSecondary }]}>{`${deck.card_count} cards`}</Text>
      </View>
    </PressableScale>
  </View>;
}

function EmptyDecks() {
  const colors = useTheme();
  return <Card tone="soft" accent="green" style={styles.empty}>
    <View style={[styles.emptyIcon, { backgroundColor: colors.green }]}><Icon name={{ ios: 'rectangle.stack.fill', android: 'style' }} size={26} color="#ffffff" /></View>
    <Body center>No decks yet.</Body>
    <Body muted center>Name a topic above and we will turn your notes into ten cards.</Body>
  </Card>;
}

const styles = StyleSheet.create({
  grid: { flexDirection: 'row', flexWrap: 'wrap', marginHorizontal: -6 },
  tileSlot: { width: '50%', padding: 6 },
  tile: { borderRadius: Radius.lg, overflow: 'hidden', borderWidth: StyleSheet.hairlineWidth, shadowOpacity: 0.06, shadowRadius: 12, shadowOffset: { width: 0, height: 6 } },
  cover: { height: 104, alignItems: 'center', justifyContent: 'center' },
  stack: { position: 'absolute', width: 64, height: 44, borderRadius: 9, alignItems: 'center', justifyContent: 'center' },
  stackBack: { backgroundColor: 'rgba(255,255,255,0.35)', transform: [{ rotateZ: '-12deg' }, { translateX: -8 }] },
  stackMid: { backgroundColor: 'rgba(255,255,255,0.6)', transform: [{ rotateZ: '7deg' }, { translateX: 6 }] },
  stackFront: { backgroundColor: '#ffffff' },
  tileText: { padding: 14, gap: 4 },
  deckName: { fontFamily: Fonts.heading, fontSize: 16, lineHeight: 21 },
  deckCount: { fontFamily: Fonts.bodySemi, fontSize: 14 },
  empty: { alignItems: 'center', gap: 8, paddingVertical: 24 },
  emptyIcon: { width: 56, height: 56, borderRadius: 18, alignItems: 'center', justifyContent: 'center', marginBottom: 6, transform: [{ rotateZ: '6deg' }] },
});
