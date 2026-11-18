import { LinearGradient } from 'expo-linear-gradient';
import { Link } from 'expo-router';
import { useFocusEffect } from 'expo-router';
import { useCallback, useEffect, useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { TopicChips } from '@/components/topic-chips';
import { Body, Button, Card, Field, Icon, Notice, PressableScale, ProgressBar, Screen } from '@/components/ui';
import { accentColors, Fonts, Radius, type Accent } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import { getJson, postJson } from '@/utils/api';
import { cached } from '@/utils/cache';
import { masteryFor } from '@/utils/mastery';

export interface DeckSummary { id: string; name: string; card_count: number }
export interface Deck { id: string; name: string; cards: { id: string; front: string; back: string }[] }

const COVERS: Accent[] = ['green', 'blue', 'amber', 'coral'];

export function Cards() {
  const [decks, setDecks] = useState<DeckSummary[]>([]);
  const [offline, setOffline] = useState(false);
  const [topic, setTopic] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [mastered, setMastered] = useState<Record<string, number>>({});

  // Mastery changes while studying a deck; refresh it whenever this tab comes back into view.
  useFocusEffect(useCallback(() => { masteryFor(decks).then(setMastered).catch(() => undefined); }, [decks]));

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
      <TopicChips value={topic} onPick={setTopic} accent="green" />
      <Button label="Make 10 cards" accent="green" icon={{ ios: 'rectangle.stack.badge.plus', android: 'library_add' }}
        busy={busy} disabled={!topic.trim() || offline} onPress={() => void generate()} />
    </Card>
    <Notice text={error} kind="error" />
    {decks.length === 0 && !error && <EmptyDecks />}
    <View style={styles.grid}>
      {decks.map((d, i) => <Link key={d.id} href={{ pathname: '/deck/[id]', params: { id: d.id } }} asChild>
        <DeckTile deck={d} accent={COVERS[i % COVERS.length]} mastered={mastered[d.id] ?? 0} />
      </Link>)}
    </View>
  </Screen>;
}

function DeckTile({ deck, accent, mastered, onPress }: { deck: DeckSummary; accent: Accent; mastered: number; onPress?: () => void }) {
  const colors = useTheme();
  const { main, deep } = accentColors(colors, accent);
  const empty = deck.card_count === 0;
  const status = empty ? 'Empty deck' : mastered === deck.card_count ? 'All mastered' : mastered > 0 ? `${mastered} of ${deck.card_count} mastered` : 'Not started';
  return <View style={styles.tileSlot}>
    <PressableScale onPress={onPress} accessibilityRole="link" accessibilityLabel={`${deck.name}, ${deck.card_count} cards, ${status}`}
      style={[styles.tile, { backgroundColor: colors.surface, borderColor: colors.border, shadowColor: colors.shadow }]}>
      <LinearGradient colors={[main, deep]} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={styles.cover}>
        <View style={[styles.glow, { backgroundColor: 'rgba(255,255,255,0.14)' }]} />
        {/* A fanned stack, tilted back in 3D like cards lying on a desk. */}
        <View style={styles.fan}>
          <View style={[styles.fanCard, styles.fanBack]} />
          <View style={[styles.fanCard, styles.fanMid]} />
          <View style={[styles.fanCard, styles.fanFront]}>
            <Text style={[styles.fanCount, { color: deep }]}>{deck.card_count}</Text>
            <Text style={[styles.fanUnit, { color: deep }]}>cards</Text>
          </View>
        </View>
        {mastered === deck.card_count && !empty && <View style={styles.badge}><Icon name={{ ios: 'star.fill', android: 'star' }} size={13} color="#f29d16" /></View>}
      </LinearGradient>
      <View style={styles.tileText}>
        <Text numberOfLines={2} style={[styles.deckName, { color: colors.text }]}>{deck.name}</Text>
        <Text style={[styles.deckCount, { color: colors.textSecondary }]}>{`${deck.card_count} cards`}</Text>
        {!empty && <ProgressBar value={mastered / deck.card_count} accent={accent} label={`${deck.name} mastery`} />}
        <Text style={[styles.status, { color: mastered > 0 ? main : colors.textFaint }]}>{status}</Text>
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
  cover: { height: 124, alignItems: 'center', justifyContent: 'center', overflow: 'hidden' },
  glow: { position: 'absolute', width: 160, height: 160, borderRadius: 999, top: -70, right: -50 },
  fan: { width: 76, height: 56, alignItems: 'center', justifyContent: 'center', transform: [{ perspective: 600 }, { rotateX: '32deg' }] },
  fanCard: { position: 'absolute', width: 76, height: 56, borderRadius: 11, alignItems: 'center', justifyContent: 'center',
    shadowColor: '#000', shadowOpacity: 0.18, shadowRadius: 8, shadowOffset: { width: 0, height: 5 } },
  fanBack: { backgroundColor: 'rgba(255,255,255,0.4)', transform: [{ rotateZ: '-16deg' }, { translateX: -14 }, { translateY: 2 }] },
  fanMid: { backgroundColor: 'rgba(255,255,255,0.7)', transform: [{ rotateZ: '-4deg' }, { translateX: -4 }] },
  fanFront: { backgroundColor: '#ffffff', transform: [{ rotateZ: '9deg' }, { translateX: 10 }, { translateY: -2 }] },
  fanCount: { fontFamily: Fonts.display, fontSize: 22, letterSpacing: -0.5, lineHeight: 24 },
  fanUnit: { fontFamily: Fonts.bodyBold, fontSize: 10, letterSpacing: 0.4, textTransform: 'uppercase' },
  badge: { position: 'absolute', top: 10, right: 10, width: 26, height: 26, borderRadius: 13, backgroundColor: '#ffffff', alignItems: 'center', justifyContent: 'center' },
  tileText: { padding: 14, gap: 6 },
  status: { fontFamily: Fonts.bodyBold, fontSize: 13 },
  deckName: { fontFamily: Fonts.heading, fontSize: 16, lineHeight: 21 },
  deckCount: { fontFamily: Fonts.bodySemi, fontSize: 14 },
  empty: { alignItems: 'center', gap: 8, paddingVertical: 24 },
  emptyIcon: { width: 56, height: 56, borderRadius: 18, alignItems: 'center', justifyContent: 'center', marginBottom: 6, transform: [{ rotateZ: '6deg' }] },
});
