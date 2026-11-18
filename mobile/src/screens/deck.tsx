import { LinearGradient } from 'expo-linear-gradient';
import { useEffect, useState, type ReactNode } from 'react';
import { ScrollView, StyleSheet, Text, useWindowDimensions, View } from 'react-native';
import Animated, { FadeIn, FadeInDown } from 'react-native-reanimated';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { CardDeck, type Answer, type DeckCard } from '@/components/card-deck';
import { Celebration } from '@/components/celebration';
import { MasteryDial, SproutArt, TrophyArt } from '@/components/illustrations';
import { Body, Icon, Notice, PressableScale, Screen, type IconName } from '@/components/ui';
import { EASE_OUT } from '@/constants/motion';
import { Fonts } from '@/constants/theme';
import { getJson } from '@/utils/api';
import { cached } from '@/utils/cache';
import { haptics } from '@/utils/haptics';
import { recordAnswer } from '@/utils/mastery';
import { recordStudy } from '@/utils/streak';
import type { Deck } from './cards';

const STAGE = ['#1fa774', '#0f3b2c'] as const;        // the logo's greens, deepened into a study stage
const INK = '#15241d';

export function DeckStudy({ id, startFlipped = false, preview }: { id: string; startFlipped?: boolean; preview?: 'strong' | 'learning' }) {
  const [deck, setDeck] = useState<Deck | null>(null);
  const [offline, setOffline] = useState(false);
  const [error, setError] = useState('');
  const [round, setRound] = useState<DeckCard[]>([]);
  const [position, setPosition] = useState(0);
  const [results, setResults] = useState<Record<string, Answer>>({});
  const [flipped, setFlipped] = useState(startFlipped);
  const [leaving, setLeaving] = useState<Answer | undefined>();
  const [pending, setPending] = useState<Answer | null>(null);

  useEffect(() => {
    cached(`deck:${id}`, () => getJson<Deck>(`/api/flashcards/${encodeURIComponent(id)}`))
      .then(r => {
        setDeck(r.value); setOffline(r.offline); setRound(r.value?.cards ?? []);
        if (preview && r.value) {                               // development only: open on the summary
          const cut = Math.round(r.value.cards.length * (preview === 'strong' ? 0.8 : 0.35));
          setResults(Object.fromEntries(r.value.cards.map((c, i) => [c.id, i < cut ? 'known' : 'learning'])));
          setPosition(r.value.cards.length);
        }
      })
      .catch(e => setError((e as Error).message));
  }, [id, preview]);

  const { height: screenHeight } = useWindowDimensions();
  const cardHeight = Math.round(Math.min(480, Math.max(320, screenHeight * 0.46)));
  const current = round[position];
  const answer = (a: Answer) => {
    if (!current) return;
    if (a === 'known') haptics.success(); else haptics.snap();
    recordAnswer(id, current.id, a === 'known').catch(() => undefined);
    recordStudy().catch(() => undefined);
    setResults(r => ({ ...r, [current.id]: a }));
    setFlipped(false);
    setPosition(p => p + 1);
  };
  // Buttons: first tell the top card which side to leave on, then answer on the next render,
  // so its exit animation already points the right way when it unmounts.
  const press = (a: Answer) => { setLeaving(a); setPending(a); };
  useEffect(() => { if (pending) { setPending(null); answer(pending); } });   // eslint-disable-line react-hooks/exhaustive-deps

  if (error) return <Screen title="Deck" accent="green"><Notice text={error} kind="error" /></Screen>;
  if (!deck) return <Screen title="Deck" accent="green"><Body muted>Loading…</Body></Screen>;
  if (deck.cards.length === 0) return <Screen title={deck.name} accent="green"><Body muted>This deck has no cards yet.</Body></Screen>;

  const restart = (cards: DeckCard[]) => { setRound(cards); setPosition(0); setResults({}); setFlipped(false); setLeaving(undefined); };
  const known = round.filter(c => results[c.id] === 'known').length;
  const learning = round.filter(c => results[c.id] === 'learning');
  const done = position >= round.length;

  return <Stage>
    <View style={styles.titleRow}>
      <Text accessibilityRole="header" numberOfLines={2} style={styles.title}>{deck.name}</Text>
      {!done && <View style={styles.counter}><Text style={styles.counterText}>{`${position + 1} / ${round.length}`}</Text></View>}
    </View>
    {offline && <Notice text="Offline: studying the copy saved on this phone." />}
    <Segments cards={round} position={position} results={results} />

    {!done ? <>
      <CardDeck cards={round.slice(position)} height={cardHeight} flipped={flipped} leaving={leaving} onFlip={() => setFlipped(f => !f)}
        onAnswer={a => { setLeaving(a); answer(a); }}
        renderFront={card => <Front card={card} deckName={deck.name} />} renderBack={card => <Back card={card} />}
        renderWaiting={() => <View style={[styles.face, styles.front]} />} />
      <View style={styles.controls}>
        <RoundButton label="Still learning" icon={{ ios: 'arrow.uturn.backward', android: 'undo' }} tone="amber" onPress={() => press('learning')} />
        <RoundButton label={flipped ? 'Show question' : 'Show answer'} icon={{ ios: 'arrow.triangle.2.circlepath', android: 'flip' }} tone="flip" large
          onPress={() => setFlipped(f => !f)} />
        <RoundButton label="Got it" icon={{ ios: 'checkmark', android: 'check' }} tone="green" onPress={() => press('known')} />
      </View>
    </> : <Summary total={round.length} known={known} learning={learning.length}
      onReview={() => restart(learning)} onAgain={() => restart(deck.cards)} />}
  </Stage>;
}

function Stage({ children }: { children: ReactNode }) {
  const insets = useSafeAreaInsets();
  return <View style={styles.flex}>
    <LinearGradient colors={STAGE} start={{ x: 0, y: 0 }} end={{ x: 0.4, y: 1 }} style={StyleSheet.absoluteFill} />
    <View pointerEvents="none" style={[styles.ring, { width: 360, height: 360, top: -140, right: -160 }]} />
    <View pointerEvents="none" style={[styles.ring, { width: 260, height: 260, bottom: 60, left: -150 }]} />
    <ScrollView contentContainerStyle={[styles.stage, { paddingTop: insets.top + 52, paddingBottom: insets.bottom + 32 }]}>{children}</ScrollView>
  </View>;
}

/** One segment per card: white when known, amber when still learning, bright for the current card. */
function Segments({ cards, position, results }: { cards: DeckCard[]; position: number; results: Record<string, Answer> }) {
  if (cards.length > 40) return null;
  return <View style={styles.segments} accessible accessibilityRole="progressbar" accessibilityLabel="Position in deck"
    accessibilityValue={{ min: 0, max: cards.length, now: Math.min(position, cards.length) }}>
    {cards.map((c, i) => <View key={c.id} style={[styles.segment, {
      backgroundColor: results[c.id] === 'known' ? '#ffffff' : results[c.id] === 'learning' ? '#ffb648' : i === position ? 'rgba(255,255,255,0.55)' : 'rgba(255,255,255,0.18)',
    }]} />)}
  </View>;
}

function Front({ card, deckName }: { card: DeckCard; deckName: string }) {
  return <View style={[styles.face, styles.front]}>
    <View style={[styles.blob, { backgroundColor: '#dbf4e8', top: -60, right: -50 }]} />
    <View style={[styles.blob, { backgroundColor: '#fff1d6', width: 120, height: 120, bottom: -50, left: -40 }]} />
    <View style={styles.faceTop}>
      <View style={[styles.chip, { backgroundColor: '#dbf4e8' }]}><Text numberOfLines={1} style={[styles.chipText, { color: '#156b4d' }]}>{deckName}</Text></View>
      <Icon name={{ ios: 'questionmark.circle.fill', android: 'help' }} size={22} color="#1fa774" />
    </View>
    <Text style={[styles.cardText, { color: INK }]}>{card.front}</Text>
    <View style={styles.hint}><Icon name={{ ios: 'hand.tap.fill', android: 'touch_app' }} size={15} color="#8a9298" />
      <Text style={styles.hintText}>Tap to flip</Text></View>
  </View>;
}

function Back({ card }: { card: DeckCard }) {
  return <View style={[styles.face, styles.backShadow]}>
    <LinearGradient colors={['#e9f8d9', '#a6e3b9']} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={[StyleSheet.absoluteFill, styles.rounded]} />
    <View style={styles.watermark}><Icon name={{ ios: 'sparkles', android: 'auto_awesome' }} size={140} color="rgba(21,107,77,0.10)" /></View>
    <View style={styles.faceTop}>
      <View style={[styles.chip, { backgroundColor: 'rgba(21,107,77,0.14)' }]}><Text style={[styles.chipText, { color: '#156b4d' }]}>Answer</Text></View>
      <Icon name={{ ios: 'lightbulb.fill', android: 'lightbulb' }} size={22} color="#156b4d" />
    </View>
    <Text style={[styles.cardText, { color: INK }]}>{card.back}</Text>
    <View style={styles.hint}><Text style={[styles.hintText, { color: '#2f6b55' }]}>Swipe right if you knew it</Text></View>
  </View>;
}

function RoundButton({ label, icon, tone, large, onPress }: { label: string; icon: IconName; tone: 'amber' | 'green' | 'flip'; large?: boolean; onPress: () => void }) {
  const size = large ? 76 : 62;
  const bg = tone === 'flip' ? '#ffffff' : tone === 'green' ? '#ffffff' : 'rgba(255,255,255,0.16)';
  const fg = tone === 'flip' ? '#156b4d' : tone === 'green' ? '#16a06a' : '#ffb648';
  return <View style={styles.roundSlot}>
    <PressableScale onPress={onPress} accessibilityLabel={label}
      style={[styles.round, { width: size, height: size, borderRadius: size / 2, backgroundColor: bg, borderColor: tone === 'amber' ? '#ffb648' : 'transparent' }]}>
      <Icon name={icon} size={large ? 30 : 24} color={fg} />
    </PressableScale>
    <Text style={styles.roundLabel}>{label}</Text>
  </View>;
}

// The summary's wave (end of deck is rare: it gets the delight budget). The illustration leads
// (its own entrance); everything else follows with shrinking gaps.
const rise = (delay: number, distance: number) => FadeInDown.duration(380).delay(delay).easing(EASE_OUT)
  .withInitialValues({ opacity: 0, transform: [{ translateY: distance }] });
const ENTER_HEADLINE = rise(160, 8);
const ENTER_TILE_A = rise(220, 6);
const ENTER_TILE_B = rise(260, 6);
const ENTER_ACTIONS = FadeIn.duration(300).delay(320);

function Summary({ total, known, learning, onReview, onAgain }: { total: number; known: number; learning: number; onReview: () => void; onAgain: () => void }) {
  const ratio = total ? known / total : 0;
  const strong = ratio >= 0.7;
  return <View style={styles.summary}>
    <Celebration play={strong} />
    {strong ? <TrophyArt size={150} /> : <SproutArt size={150} />}
    <Animated.View entering={ENTER_HEADLINE} style={styles.headline}>
      <Text accessibilityRole="header" style={styles.summaryTitle}>{`You know ${known} of ${total}`}</Text>
      <Text style={styles.summaryBody}>{ratio === 1 ? 'Every card. Brilliant work.' : strong ? 'Strong round. One quick review and they are all yours.' : 'Every review makes them stick. Go again on the rest.'}</Text>
    </Animated.View>
    <View style={styles.statsRow}>
      <MasteryDial value={ratio} color="#1fa774" track="#cfd8d3" size={104}>
        <Text style={styles.dialValue}>{`${Math.round(ratio * 100)}%`}</Text>
        <Text style={styles.dialLabel}>mastered</Text>
      </MasteryDial>
      <View style={styles.tiles}>
        <Animated.View entering={ENTER_TILE_A} accessible accessibilityLabel={`${known} got it`} style={[styles.tile, { backgroundColor: '#ddf5ea' }]}>
          <View style={[styles.tileIcon, { backgroundColor: '#1fa774' }]}><Icon name={{ ios: 'checkmark', android: 'check' }} size={14} color="#ffffff" /></View>
          <View><Text style={[styles.tileValue, { color: '#156b4d' }]}>{known}</Text><Text style={[styles.tileLabel, { color: '#156b4d' }]}>got it</Text></View>
        </Animated.View>
        <Animated.View entering={ENTER_TILE_B} accessible accessibilityLabel={`${learning} still learning`} style={[styles.tile, { backgroundColor: '#fff1d6' }]}>
          <View style={[styles.tileIcon, { backgroundColor: '#f29d16' }]}><Icon name={{ ios: 'arrow.uturn.backward', android: 'undo' }} size={13} color="#ffffff" /></View>
          <View><Text style={[styles.tileValue, { color: '#a35a04' }]}>{learning}</Text><Text style={[styles.tileLabel, { color: '#a35a04' }]}>still learning</Text></View>
        </Animated.View>
      </View>
    </View>
    <Animated.View entering={ENTER_ACTIONS} style={styles.actions}>
      <PressableScale onPress={learning > 0 ? onReview : onAgain}
        accessibilityLabel={learning > 0 ? `Review the ${learning} still learning` : 'Study the whole deck again'}>
        <View style={styles.primaryShadow}>
          <LinearGradient colors={['#1fa774', '#156b4d']} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={styles.primary}>
            <Icon name={learning > 0 ? { ios: 'bolt.fill', android: 'bolt' } : { ios: 'arrow.clockwise', android: 'refresh' }} size={18} color="#ffffff" />
            <Text style={styles.primaryText}>{learning > 0 ? `Review the ${learning} still learning` : 'Study the whole deck again'}</Text>
          </LinearGradient>
        </View>
      </PressableScale>
      {learning > 0 && <PressableScale onPress={onAgain} accessibilityLabel="Study the whole deck again" style={styles.link}>
        <Text style={styles.linkText}>Study the whole deck again</Text>
      </PressableScale>}
    </Animated.View>
  </View>;
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  stage: { paddingHorizontal: 20, gap: 18 },
  ring: { position: 'absolute', borderRadius: 999, borderWidth: 28, borderColor: 'rgba(255,255,255,0.06)' },
  titleRow: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  title: { flex: 1, fontFamily: Fonts.display, fontSize: 30, letterSpacing: -0.8, color: '#ffffff' },
  counter: { backgroundColor: 'rgba(255,255,255,0.16)', paddingHorizontal: 12, paddingVertical: 6, borderRadius: 999 },
  counterText: { fontFamily: Fonts.bodyBold, fontSize: 15, color: '#ffffff', fontVariant: ['tabular-nums'] },
  segments: { flexDirection: 'row', gap: 4, marginBottom: 6 },
  segment: { flex: 1, height: 6, borderRadius: 3 },
  face: { flex: 1, borderRadius: 30, padding: 24, justifyContent: 'center', overflow: 'hidden' },
  front: { backgroundColor: '#ffffff', shadowColor: '#06140e', shadowOpacity: 0.3, shadowRadius: 26, shadowOffset: { width: 0, height: 16 } },
  backShadow: { shadowColor: '#06140e', shadowOpacity: 0.3, shadowRadius: 26, shadowOffset: { width: 0, height: 16 } },
  rounded: { borderRadius: 30 },
  blob: { position: 'absolute', width: 170, height: 170, borderRadius: 999, opacity: 0.8 },
  watermark: { position: 'absolute', right: -20, bottom: -20 },
  faceTop: { position: 'absolute', top: 22, left: 22, right: 22, flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  chip: { paddingHorizontal: 11, paddingVertical: 5, borderRadius: 999, maxWidth: '75%' },
  chipText: { fontFamily: Fonts.bodyBold, fontSize: 13 },
  cardText: { fontFamily: Fonts.heading, fontSize: 27, lineHeight: 35, letterSpacing: -0.5, textAlign: 'center' },
  hint: { position: 'absolute', bottom: 20, left: 0, right: 0, flexDirection: 'row', gap: 6, justifyContent: 'center', alignItems: 'center' },
  hintText: { fontFamily: Fonts.bodySemi, fontSize: 14, color: '#8a9298' },
  controls: { flexDirection: 'row', justifyContent: 'space-evenly', alignItems: 'flex-end' },
  roundSlot: { alignItems: 'center', justifyContent: 'flex-end', gap: 8, minWidth: 90 },
  round: { alignItems: 'center', justifyContent: 'center', borderWidth: 2, shadowColor: '#06140e', shadowOpacity: 0.25, shadowRadius: 14, shadowOffset: { width: 0, height: 8 } },
  roundLabel: { fontFamily: Fonts.bodyBold, fontSize: 14, color: '#ffffff' },
  summary: { backgroundColor: '#ffffff', borderRadius: 32, paddingHorizontal: 22, paddingTop: 18, paddingBottom: 20, alignItems: 'center', gap: 14, overflow: 'visible',
    shadowColor: '#06140e', shadowOpacity: 0.3, shadowRadius: 26, shadowOffset: { width: 0, height: 16 } },
  headline: { alignItems: 'center', gap: 6 },
  summaryTitle: { fontFamily: Fonts.display, fontSize: 30, letterSpacing: -0.9, color: INK, textAlign: 'center' },
  summaryBody: { fontFamily: Fonts.body, fontSize: 17, lineHeight: 24, color: '#5d666c', textAlign: 'center', maxWidth: 300 },
  statsRow: { flexDirection: 'row', alignItems: 'center', gap: 16, alignSelf: 'stretch', justifyContent: 'center', marginVertical: 4 },
  dialValue: { fontFamily: Fonts.display, fontSize: 24, letterSpacing: -0.6, color: INK },
  dialLabel: { fontFamily: Fonts.bodySemi, fontSize: 12, color: '#5d666c', marginTop: -2 },
  tiles: { flex: 1, gap: 10, maxWidth: 190 },
  tile: { flexDirection: 'row', alignItems: 'center', gap: 12, paddingHorizontal: 14, paddingVertical: 10, borderRadius: 18 },
  tileIcon: { width: 28, height: 28, borderRadius: 14, alignItems: 'center', justifyContent: 'center' },
  tileValue: { fontFamily: Fonts.display, fontSize: 22, letterSpacing: -0.5, lineHeight: 25 },
  tileLabel: { fontFamily: Fonts.bodySemi, fontSize: 13 },
  actions: { alignSelf: 'stretch', gap: 4, marginTop: 4 },
  primaryShadow: { borderRadius: 18, backgroundColor: '#156b4d', shadowColor: '#156b4d', shadowOpacity: 0.35, shadowRadius: 14, shadowOffset: { width: 0, height: 8 } },
  primary: { minHeight: 56, borderRadius: 18, flexDirection: 'row', gap: 10, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 18 },
  primaryText: { fontFamily: Fonts.heading, fontSize: 17, color: '#ffffff' },
  link: { minHeight: 44, alignItems: 'center', justifyContent: 'center' },
  linkText: { fontFamily: Fonts.bodyBold, fontSize: 16, color: '#156b4d' },
});
