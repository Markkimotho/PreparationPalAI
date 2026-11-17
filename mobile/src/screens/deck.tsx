import { LinearGradient } from 'expo-linear-gradient';
import { useEffect, useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import Animated, { withTiming } from 'react-native-reanimated';

import { FlipCard } from '@/components/flip-card';
import { Body, Button, Icon, Notice, ProgressBar, Screen } from '@/components/ui';
import { EASE_OUT } from '@/constants/motion';
import { Fonts } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import { getJson } from '@/utils/api';
import { cached } from '@/utils/cache';
import { recordStudy } from '@/utils/streak';
import type { Deck } from './cards';

// The next card settles in from just behind (never from nothing): 200ms, strong ease-out.
const settleIn = () => {
  'worklet';
  const timing = { duration: 200, easing: EASE_OUT };
  return { initialValues: { opacity: 0, transform: [{ scale: 0.95 }] }, animations: { opacity: withTiming(1, timing), transform: [{ scale: withTiming(1, timing) }] } };
};

export function DeckStudy({ id }: { id: string }) {
  const colors = useTheme();
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

  if (error) return <Screen title="Deck" accent="green"><Notice text={error} kind="error" /></Screen>;
  if (!deck) return <Screen title="Deck" accent="green"><Body muted>Loading…</Body></Screen>;
  if (deck.cards.length === 0) return <Screen title={deck.name} accent="green"><Body muted>This deck has no cards yet.</Body></Screen>;
  const card = deck.cards[index];
  const total = deck.cards.length;
  const move = (step: number) => { setFlipped(false); setIndex(i => (i + step + total) % total); };
  const flip = () => { if (!flipped) recordStudy().catch(() => undefined); setFlipped(f => !f); };

  return <Screen title={deck.name} subtitle={`Card ${index + 1} of ${total}`} accent="green">
    {offline && <Notice text="Offline: studying the copy saved on this phone." />}
    <ProgressBar value={(index + 1) / total} accent="green" label="Position in deck" />
    <Animated.View key={card.id} entering={settleIn}>
      <FlipCard flipped={flipped} onFlip={flip} onSwipe={direction => move(direction === -1 ? 1 : -1)}
        front={<View style={[styles.face, { backgroundColor: colors.surface, borderColor: colors.border, shadowColor: colors.shadow }]}>
          <View style={[styles.tag, { backgroundColor: colors.greenSoft }]}><Text style={[styles.tagText, { color: colors.greenDeep }]}>Question</Text></View>
          <Text style={[styles.cardText, { color: colors.text }]}>{card.front}</Text>
          <View style={styles.tapHint}><Icon name={{ ios: 'hand.tap.fill', android: 'touch_app' }} size={16} color={colors.textFaint} />
            <Text style={[styles.hintText, { color: colors.textFaint }]}>Tap to flip, swipe for the next card</Text></View>
        </View>}
        back={<View style={[styles.face, { shadowColor: colors.greenDeep }]}>
          <LinearGradient colors={[colors.green, colors.greenDeep]} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={[StyleSheet.absoluteFill, styles.round]} />
          <View style={[styles.tag, { backgroundColor: 'rgba(255,255,255,0.22)' }]}><Text style={[styles.tagText, { color: '#ffffff' }]}>Answer</Text></View>
          <Text style={[styles.cardText, { color: '#ffffff' }]}>{card.back}</Text>
        </View>} />
    </Animated.View>
    <View style={styles.controls}>
      <View style={styles.side}><Button label="Previous" variant="secondary" accent="green" icon={{ ios: 'chevron.left', android: 'chevron_left' }} onPress={() => move(-1)} /></View>
      <View style={styles.side}><Button label="Next" variant="secondary" accent="green" icon={{ ios: 'chevron.right', android: 'chevron_right' }} onPress={() => move(1)} /></View>
    </View>
    <Button label={flipped ? 'Show question' : 'Show answer'} accent="green" icon={{ ios: 'arrow.triangle.2.circlepath', android: 'flip' }} onPress={flip} />
  </Screen>;
}

const styles = StyleSheet.create({
  face: { flex: 1, borderRadius: 26, padding: 24, justifyContent: 'center', gap: 16, borderWidth: StyleSheet.hairlineWidth, borderColor: 'transparent',
    shadowOpacity: 0.14, shadowRadius: 24, shadowOffset: { width: 0, height: 12 }, elevation: 4 },
  round: { borderRadius: 26 },
  tag: { position: 'absolute', top: 20, left: 20, paddingHorizontal: 10, paddingVertical: 5, borderRadius: 999 },
  tagText: { fontFamily: Fonts.bodyBold, fontSize: 13, letterSpacing: 0.3 },
  cardText: { fontFamily: Fonts.heading, fontSize: 26, lineHeight: 33, letterSpacing: -0.4, textAlign: 'center' },
  tapHint: { position: 'absolute', bottom: 18, left: 0, right: 0, flexDirection: 'row', gap: 6, justifyContent: 'center', alignItems: 'center' },
  hintText: { fontFamily: Fonts.bodySemi, fontSize: 13 },
  controls: { flexDirection: 'row', gap: 12 },
  side: { flex: 1 },
});
