/**
 * The four welcome illustrations, drawn with views and moved in 3D with perspective transforms.
 * Every loop runs on the UI thread, only while its slide is showing, and not at all when the
 * system asks for reduced motion (the illustration then holds a still, readable pose).
 * Decorative: hidden from screen readers; the slide's title and text carry the meaning.
 */
import { LinearGradient } from 'expo-linear-gradient';
import { useEffect, type ReactNode } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import Animated, {
  cancelAnimation, Easing, interpolate, useAnimatedStyle, useSharedValue, withDelay, withRepeat, withSequence, withTiming,
  type SharedValue,
} from 'react-native-reanimated';

import { Icon } from '@/components/ui';
import { EASE_IN_OUT } from '@/constants/motion';
import { Fonts, type Palette } from '@/constants/theme';

export interface IllustrationProps { size: number; active: boolean; reduced: boolean; colors: Palette }

/** Drive `value` with `animation` while active; otherwise stop and hold `rest`. */
function useLoop(active: boolean, reduced: boolean, rest: number, animation: () => number): SharedValue<number> {
  const value = useSharedValue(rest);
  useEffect(() => {
    if (active && !reduced) value.set(animation());
    else { cancelAnimation(value); value.set(withTiming(rest, { duration: 300 })); }
    return () => cancelAnimation(value);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, reduced]);
  return value;
}

const Decorative = ({ children, size }: { children: ReactNode; size: number }) =>
  <View accessibilityElementsHidden importantForAccessibility="no-hide-descendants" style={{ width: size, height: size, alignItems: 'center', justifyContent: 'center' }}>{children}</View>;

/** Slide 1: notes as a stack of sheets in isometric 3D; the layers breathe apart and back. */
export function NotesStack({ size, active, reduced, colors }: IllustrationProps) {
  const lift = useLoop(active, reduced, 0.5, () =>
    withRepeat(withSequence(withTiming(1, { duration: 1600, easing: EASE_IN_OUT }), withTiming(0, { duration: 1600, easing: EASE_IN_OUT })), -1));
  const sheet = size * 0.62;
  const layers = [
    { tint: colors.blueSoft, lines: colors.blue, depth: 0 },
    { tint: colors.surface, lines: colors.textFaint, depth: 1 },
    { tint: colors.surface, lines: colors.textFaint, depth: 2 },
  ];
  return <Decorative size={size}>
    <View style={{ width: sheet, height: sheet * 1.1 }}>
      {layers.map(l => <Layer key={l.depth} depth={l.depth} lift={lift} size={sheet}>
        <View style={[styles.sheet, { backgroundColor: l.tint, borderColor: colors.border, shadowColor: colors.shadow }]}>
          {[0.8, 0.95, 0.6, 0.85, 0.5].map((w, i) => <View key={i} style={[styles.line, { width: `${w * 100}%`, backgroundColor: l.lines, opacity: l.depth === 2 ? 0.35 : 0.22 }]} />)}
          {l.depth === 2 && <View style={[styles.highlight, { backgroundColor: colors.amber }]} />}
        </View>
      </Layer>)}
    </View>
    <Bob lift={lift} style={[styles.badge, { right: size * 0.08, top: size * 0.06, backgroundColor: colors.blue, shadowColor: colors.blueDeep }]}>
      <Icon name={{ ios: 'sparkles', android: 'auto_awesome' }} size={26} color="#ffffff" />
    </Bob>
  </Decorative>;
}

function Layer({ depth, lift, size, children }: { depth: number; lift: SharedValue<number>; size: number; children: ReactNode }) {
  const style = useAnimatedStyle(() => ({
    transform: [{ perspective: 900 }, { translateY: -depth * interpolate(lift.get(), [0, 1], [size * 0.12, size * 0.22]) + size * 0.2 },
      { rotateX: '58deg' }, { rotateZ: '-38deg' }],
  }));
  return <Animated.View style={[StyleSheet.absoluteFill, style]}>{children}</Animated.View>;
}

function Bob({ lift, style, children }: { lift: SharedValue<number>; style: object; children: ReactNode }) {
  const bob = useAnimatedStyle(() => ({ transform: [{ translateY: interpolate(lift.get(), [0, 1], [4, -8]) }] }));
  return <Animated.View style={[style, bob]}>{children}</Animated.View>;
}

/** Slide 2: a flashcard that flips on its Y axis, question to answer, on a small deck. */
export function FlipCard({ size, active, reduced, colors }: IllustrationProps) {
  // 0 → 1 → 2 is 0° → 180° → 360°; the repeat restarts at 0°, which looks identical to 360°.
  const flip = useLoop(active, reduced, 0, () => withRepeat(withSequence(
    withDelay(1300, withTiming(1, { duration: 650, easing: EASE_IN_OUT })),
    withDelay(1300, withTiming(2, { duration: 650, easing: EASE_IN_OUT }))), -1));
  const card = { width: size * 0.66, height: size * 0.46 };
  const front = useAnimatedStyle(() => ({ transform: [{ perspective: 1000 }, { rotateY: `${flip.get() * 180}deg` }] }));
  const back = useAnimatedStyle(() => ({ transform: [{ perspective: 1000 }, { rotateY: `${flip.get() * 180 + 180}deg` }] }));
  const lean = useAnimatedStyle(() => ({ transform: [{ rotateZ: `${interpolate(flip.get() % 1, [0, 0.5, 1], [-4, 2, -4])}deg` }] }));
  return <Decorative size={size}>
    <View style={[styles.deckCard, card, { backgroundColor: colors.amberSoft, transform: [{ rotateZ: '-12deg' }, { translateX: -size * 0.06 }, { translateY: size * 0.05 }] }]} />
    <View style={[styles.deckCard, card, { backgroundColor: colors.surface, borderColor: colors.border, transform: [{ rotateZ: '8deg' }, { translateX: size * 0.05 }, { translateY: size * 0.03 }] }]} />
    <Animated.View style={[card, lean]}>
      <Animated.View style={[styles.face, card, { backgroundColor: colors.surface, shadowColor: colors.amberDeep }, front]}>
        <View style={[styles.tag, { backgroundColor: colors.amberSoft }]}><Text style={[styles.tagText, { color: colors.amberDeep }]}>Q</Text></View>
        <Text style={[styles.cardText, { color: colors.text }]}>What makes ATP?</Text>
      </Animated.View>
      <Animated.View style={[styles.face, card, styles.faceOverlay, back]}>
        <LinearGradient colors={[colors.amber, colors.amberDeep]} style={[styles.gradientFill, { borderRadius: 18 }]} />
        <View style={[styles.tag, { backgroundColor: 'rgba(255,255,255,0.25)' }]}><Text style={[styles.tagText, { color: '#ffffff' }]}>A</Text></View>
        <Text style={[styles.cardText, { color: '#ffffff' }]}>Mitochondria</Text>
      </Animated.View>
    </Animated.View>
  </Decorative>;
}

/** Slide 3: answer choices tilted in 3D with the right one marked, and a score medal spinning like a coin. */
export function Practice({ size, active, reduced, colors }: IllustrationProps) {
  const spin = useLoop(active, reduced, 0, () => withRepeat(withTiming(1, { duration: 4200, easing: Easing.linear }), -1));
  const medal = size * 0.32;
  const front = useAnimatedStyle(() => ({ transform: [{ perspective: 700 }, { rotateY: `${spin.get() * 360}deg` }] }));
  const back = useAnimatedStyle(() => ({ transform: [{ perspective: 700 }, { rotateY: `${spin.get() * 360 + 180}deg` }] }));
  const choices = [{ l: 'A', t: 'Binary search', ok: false }, { l: 'B', t: 'O(log n)', ok: true }, { l: 'C', t: 'Hash table', ok: false }];
  return <Decorative size={size}>
    <View style={{ width: size * 0.78, gap: 10, transform: [{ perspective: 900 }, { rotateX: '22deg' }, { rotateZ: '-4deg' }, { translateY: size * 0.08 }] }}>
      {choices.map(c => <View key={c.l} style={[styles.choice, {
        backgroundColor: c.ok ? colors.greenSoft : colors.surface, borderColor: c.ok ? colors.green : colors.border, shadowColor: colors.shadow,
      }]}>
        <View style={[styles.choiceLetter, { backgroundColor: c.ok ? colors.green : colors.backgroundElement }]}>
          {c.ok ? <Icon name={{ ios: 'checkmark', android: 'check' }} size={13} color="#ffffff" />
            : <Text style={[styles.choiceLetterText, { color: colors.textSecondary }]}>{c.l}</Text>}
        </View>
        <Text style={[styles.choiceText, { color: colors.text }]}>{c.t}</Text>
      </View>)}
    </View>
    <View style={[styles.medalSpot, { width: medal, height: medal, right: size * 0.04, top: size * 0.02 }]}>
      <Animated.View style={[styles.coin, { width: medal, height: medal, borderRadius: medal / 2 }, front]}>
        <LinearGradient colors={[colors.green, colors.greenDeep]} style={[styles.gradientFill, { borderRadius: medal / 2 }]} />
        <Text style={[styles.medalText, { fontSize: medal * 0.34 }]}>A+</Text>
      </Animated.View>
      <Animated.View style={[styles.coin, styles.faceOverlay, { width: medal, height: medal, borderRadius: medal / 2 }, back]}>
        <LinearGradient colors={[colors.amber, colors.amberDeep]} style={[styles.gradientFill, { borderRadius: medal / 2 }]} />
        <Text style={[styles.medalText, { fontSize: medal * 0.26 }]}>92%</Text>
      </Animated.View>
    </View>
  </Decorative>;
}

/** Slide 4: credits orbiting the logo mark on a tilted ellipse; items behind the mark pass under it. */
export function CreditOrbit({ size, active, reduced, colors }: IllustrationProps) {
  const angle = useLoop(active, reduced, 0.15, () => withRepeat(withTiming(1, { duration: 9000, easing: Easing.linear }), -1));
  const mark = size * 0.34;
  const tokens = [
    { icon: { ios: 'star.fill', android: 'star' }, bg: colors.amber, label: '' },
    { icon: null, bg: colors.coral, label: '500' },
    { icon: { ios: 'book.fill', android: 'menu_book' }, bg: colors.blue, label: '' },
  ] as const;
  const pass = (front: boolean) => tokens.map((t, k) => <Token key={`${front}-${k}`} angle={angle} phase={k / tokens.length} front={front} size={size}>
    <View style={[styles.token, { backgroundColor: t.bg, shadowColor: t.bg }]}>
      {t.icon ? <Icon name={t.icon} size={20} color="#ffffff" /> : <Text style={styles.tokenText}>{t.label}</Text>}
    </View>
  </Token>);
  return <Decorative size={size}>
    <View style={[styles.ring, { width: size * 0.9, height: size * 0.32, borderColor: colors.coral }]} />
    {pass(false)}
    <View style={[styles.mark, { width: mark, height: mark, backgroundColor: colors.brand, shadowColor: colors.brand }]}>
      <View style={[styles.markInner, { width: mark * 0.62, height: mark * 0.62, backgroundColor: colors.mint }]}>
        <Icon name={{ ios: 'checkmark', android: 'check' }} size={mark * 0.3} color={colors.brand} />
      </View>
    </View>
    {pass(true)}
  </Decorative>;
}

function Token({ angle, phase, front, size, children }: { angle: SharedValue<number>; phase: number; front: boolean; size: number; children: ReactNode }) {
  const style = useAnimatedStyle(() => {
    const theta = (angle.get() + phase) * Math.PI * 2;
    const depth = Math.sin(theta);                       // -1 behind the mark, +1 in front
    const visible = front ? depth >= 0 : depth < 0;
    return {
      opacity: visible ? interpolate(depth, [-1, 0, 1], [0.55, 0.85, 1]) : 0,
      transform: [{ translateX: Math.cos(theta) * size * 0.42 }, { translateY: depth * size * 0.14 },
        { scale: interpolate(depth, [-1, 1], [0.72, 1.12]) }],
    };
  });
  return <Animated.View pointerEvents="none" style={[styles.tokenSpot, style]}>{children}</Animated.View>;
}

const styles = StyleSheet.create({
  sheet: { flex: 1, borderRadius: 16, borderWidth: StyleSheet.hairlineWidth, padding: 16, gap: 9, shadowOpacity: 0.12, shadowRadius: 18, shadowOffset: { width: 0, height: 10 } },
  line: { height: 7, borderRadius: 4 },
  highlight: { position: 'absolute', left: 16, top: 30, width: '45%', height: 9, borderRadius: 5, opacity: 0.85 },
  badge: { position: 'absolute', width: 56, height: 56, borderRadius: 28, alignItems: 'center', justifyContent: 'center', shadowOpacity: 0.35, shadowRadius: 14, shadowOffset: { width: 0, height: 8 } },
  deckCard: { position: 'absolute', borderRadius: 18, borderWidth: StyleSheet.hairlineWidth, borderColor: 'transparent' },
  face: { borderRadius: 18, padding: 18, justifyContent: 'center', gap: 10, backfaceVisibility: 'hidden', shadowOpacity: 0.25, shadowRadius: 18, shadowOffset: { width: 0, height: 10 }, overflow: 'visible' },
  faceOverlay: { position: 'absolute', top: 0, left: 0, backfaceVisibility: 'hidden' },
  gradientFill: { position: 'absolute', top: 0, left: 0, right: 0, bottom: 0 },
  tag: { alignSelf: 'flex-start', width: 28, height: 28, borderRadius: 14, alignItems: 'center', justifyContent: 'center' },
  tagText: { fontFamily: Fonts.display, fontSize: 14 },
  cardText: { fontFamily: Fonts.heading, fontSize: 20, letterSpacing: -0.3 },
  choice: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingHorizontal: 12, height: 50, borderRadius: 14, borderWidth: 1.5, shadowOpacity: 0.08, shadowRadius: 10, shadowOffset: { width: 0, height: 6 } },
  choiceLetter: { width: 26, height: 26, borderRadius: 13, alignItems: 'center', justifyContent: 'center' },
  choiceLetterText: { fontFamily: Fonts.heading, fontSize: 13 },
  choiceText: { fontFamily: Fonts.bodySemi, fontSize: 16 },
  medalSpot: { position: 'absolute' },
  coin: { alignItems: 'center', justifyContent: 'center', backfaceVisibility: 'hidden', shadowColor: '#000', shadowOpacity: 0.2, shadowRadius: 12, shadowOffset: { width: 0, height: 8 } },
  medalText: { fontFamily: Fonts.display, color: '#ffffff', letterSpacing: -0.5 },
  ring: { position: 'absolute', borderWidth: 2, borderRadius: 999, opacity: 0.25, borderStyle: 'dashed' },
  mark: { borderRadius: 26, alignItems: 'center', justifyContent: 'center', transform: [{ rotateZ: '45deg' }], shadowOpacity: 0.3, shadowRadius: 16, shadowOffset: { width: 0, height: 10 } },
  markInner: { borderRadius: 14, alignItems: 'center', justifyContent: 'center', transform: [{ rotateZ: '-45deg' }] },
  tokenSpot: { position: 'absolute' },
  token: { width: 48, height: 48, borderRadius: 24, alignItems: 'center', justifyContent: 'center', shadowOpacity: 0.35, shadowRadius: 10, shadowOffset: { width: 0, height: 6 } },
  tokenText: { fontFamily: Fonts.display, fontSize: 14, color: '#ffffff' },
});
