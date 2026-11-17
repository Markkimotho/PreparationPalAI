/**
 * The welcome carousel shown before sign-in.
 *
 * Motion (choreograph + animate-expo skills):
 *  - Swiping is a native paging scroll view: real momentum and velocity handoff for free. One
 *    shared value (the scroll offset) drives everything else on the UI thread: each slide's
 *    illustration turns in 3D (rotateY ±40° with perspective) and recedes, title and text move
 *    at different speeds (the illustration leads at 130% of the scroll so neighbours stay hidden;
 *    the title follows at 85% and the text at 70%, which reads as depth),
 *    the background blends between the slides' colours, and the dot indicator follows the finger.
 *  - First paint is one wave: illustration (lead) 0ms, title 120ms, text 200ms, controls 260ms.
 *  - Each slide's illustration loops only while that slide is showing.
 *  - Reduced motion: no loops, no 3D or parallax; slides crossfade, entrances are skipped.
 *  - One selection haptic per page change, fired when the page settles.
 */
import { useLocalSearchParams } from 'expo-router';
import { useEffect, useRef, useState } from 'react';
import { StyleSheet, Text, useWindowDimensions, View, type NativeScrollEvent, type NativeSyntheticEvent } from 'react-native';
import Animated, {
  Extrapolation, FadeIn, FadeInDown, interpolate, interpolateColor, useAnimatedRef, useAnimatedScrollHandler, useAnimatedStyle,
  useReducedMotion, useSharedValue, withTiming, type SharedValue,
} from 'react-native-reanimated';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { Button, Icon, Notice, PressableScale } from '@/components/ui';
import { EASE_OUT } from '@/constants/motion';
import { accentColors, Fonts, Radius, type Accent, type Palette } from '@/constants/theme';
import { useSession } from '@/hooks/use-session';
import { useTheme } from '@/hooks/use-theme';
import { haptics } from '@/utils/haptics';
import { CreditOrbit, FlipCard, NotesStack, Practice, type IllustrationProps } from './illustrations';

export const SLIDES: { title: string; body: string; accent: Accent; Illustration: (p: IllustrationProps) => React.ReactNode }[] = [
  { title: 'Study deeply', body: 'Ask anything about your own notes. Clear answers, with the sources they came from.', accent: 'blue', Illustration: NotesStack },
  { title: 'Prepare confidently', body: 'Flashcards that flip and quizzes that explain, made from what you are learning.', accent: 'amber', Illustration: FlipCard },
  { title: 'Practise like it’s real', body: 'Exam, interview and recap practice with a coach that scores you and shows what to do next.', accent: 'green', Illustration: Practice },
  { title: 'Start free', body: 'Confirm your email and get 500 free credits. After that, top up only when you need to.', accent: 'coral', Illustration: CreditOrbit },
];
const LAST = SLIDES.length - 1;
const DOT_STEP = 24;

// The entrance wave (one entrance per element, shrinking gaps so it reads as one motion).
const ENTER_LEAD = () => {
  'worklet';
  const timing = { duration: 600, easing: EASE_OUT };
  return { initialValues: { opacity: 0, transform: [{ scale: 0.94 }] }, animations: { opacity: withTiming(1, timing), transform: [{ scale: withTiming(1, timing) }] } };
};
const ENTER_TITLE = FadeInDown.duration(500).delay(120).easing(EASE_OUT).withInitialValues({ opacity: 0, transform: [{ translateY: 12 }] });
const ENTER_BODY = FadeInDown.duration(500).delay(200).easing(EASE_OUT).withInitialValues({ opacity: 0, transform: [{ translateY: 8 }] });
const ENTER_CONTROLS = FadeInDown.duration(450).delay(260).easing(EASE_OUT).withInitialValues({ opacity: 0, transform: [{ translateY: 6 }] });
const ENTER_DECORATION = FadeIn.duration(400);

export function Welcome() {
  const colors = useTheme();
  const { width, height } = useWindowDimensions();
  const insets = useSafeAreaInsets();
  const reduced = useReducedMotion();
  const { signIn, notice, error } = useSession();
  // Development builds only: preparationpal://sign-in?slide=2 opens on a slide (screenshots, review).
  const { slide } = useLocalSearchParams<{ slide?: string }>();
  const initial = __DEV__ && slide ? Math.max(0, Math.min(LAST, Number(slide) || 0)) : 0;
  const [page, setPage] = useState(initial);
  const [busy, setBusy] = useState(false);
  const scroller = useAnimatedRef<Animated.ScrollView>();
  const scrollX = useSharedValue(initial * width);
  const lastPage = useRef(initial);

  const onScroll = useAnimatedScrollHandler({ onScroll: e => { scrollX.set(e.contentOffset.x); } });
  const settle = (next: number) => {
    const clamped = Math.max(0, Math.min(LAST, next));
    if (clamped !== lastPage.current) { lastPage.current = clamped; haptics.select(); }
    setPage(clamped);
  };
  const goTo = (next: number) => {
    scroller.current?.scrollTo({ x: next * width, animated: !reduced });
    settle(next);
  };
  // A dev deep link to another slide while this screen is open moves to it.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { if (initial !== lastPage.current) goTo(initial); }, [initial]);
  const onSettled = (e: NativeSyntheticEvent<NativeScrollEvent>) => settle(Math.round(e.nativeEvent.contentOffset.x / width));
  const start = async () => { setBusy(true); await signIn(); setBusy(false); };

  const tints = SLIDES.map(s => accentColors(colors, s.accent).soft);
  const inputs = SLIDES.map((_, i) => i * width);
  const background = useAnimatedStyle(() => ({ backgroundColor: interpolateColor(scrollX.get(), inputs, tints) }));
  const stage = Math.min(width - 64, height * 0.4, 340);

  return <Animated.View style={[styles.flex, background]}>
    <Blobs scrollX={scrollX} width={width} colors={colors} />
    <Animated.View entering={ENTER_DECORATION} style={[styles.topBar, { paddingTop: insets.top + 8 }]}>
      <View style={styles.brand} accessible accessibilityRole="header" accessibilityLabel="PreparationPalAI">
        <View style={[styles.logo, { backgroundColor: colors.brand }]}><View style={[styles.logoInner, { backgroundColor: colors.mint }]} /></View>
        <Text style={[styles.wordmark, { color: colors.text }]}>PreparationPalAI</Text>
      </View>
      {page < LAST && <PressableScale onPress={() => goTo(LAST)} accessibilityLabel="Skip" style={styles.skip}>
        <Text style={[styles.skipText, { color: colors.textSecondary }]}>Skip</Text>
      </PressableScale>}
    </Animated.View>

    <Animated.ScrollView testID="welcome-slides" ref={scroller} horizontal pagingEnabled showsHorizontalScrollIndicator={false} onScroll={onScroll}
      scrollEventThrottle={16} onMomentumScrollEnd={onSettled} style={styles.flex} decelerationRate="fast" contentOffset={{ x: initial * width, y: 0 }}>
      {SLIDES.map((s, i) => <Slide key={s.title} index={i} slide={s} scrollX={scrollX} width={width} stage={stage}
        active={page === i} reduced={reduced} colors={colors} />)}
    </Animated.ScrollView>

    <Animated.View entering={ENTER_CONTROLS} style={[styles.controls, { paddingBottom: insets.bottom + 16 }]}>
      <Dots scrollX={scrollX} width={width} colors={colors} />
      <Notice text={notice} />
      <Notice text={error} kind="error" />
      {page < LAST
        ? <Button label="Next" icon={{ ios: 'arrow.right', android: 'arrow_forward' }} onPress={() => goTo(page + 1)} />
        : <Button label="Get started" icon={{ ios: 'sparkles', android: 'auto_awesome' }} busy={busy} onPress={() => void start()} />}
      <Button label="I already have an account" variant="ghost" compact disabled={busy} onPress={() => void start()} />
    </Animated.View>
  </Animated.View>;
}

function Slide({ index, slide, scrollX, width, stage, active, reduced, colors }: {
  index: number; slide: (typeof SLIDES)[number]; scrollX: SharedValue<number>; width: number; stage: number;
  active: boolean; reduced: boolean; colors: Palette;
}) {
  const range = [(index - 1) * width, index * width, (index + 1) * width];
  const art = useAnimatedStyle(() => {
    const x = scrollX.get();
    const opacity = interpolate(x, range, [0, 1, 0], Extrapolation.CLAMP);
    if (reduced) return { opacity };
    return {
      opacity,
      transform: [{ perspective: 900 },
        { translateX: interpolate(x, range, [width * 0.3, 0, -width * 0.3], Extrapolation.CLAMP) },
        { rotateY: `${interpolate(x, range, [40, 0, -40], Extrapolation.CLAMP)}deg` },
        { scale: interpolate(x, range, [0.78, 1, 0.78], Extrapolation.CLAMP) }],
    };
  });
  // Reanimated tracks only shared values read directly inside useAnimatedStyle, so each style
  // reads scrollX itself and passes the number in (reading it inside a helper never updates).
  const text = (x: number, lag: number) => {
    'worklet';
    const opacity = interpolate(x, [(index - 0.6) * width, index * width, (index + 0.6) * width], [0, 1, 0], Extrapolation.CLAMP);
    return reduced ? { opacity } : { opacity, transform: [{ translateX: interpolate(x, range, [-width * lag, 0, width * lag], Extrapolation.CLAMP) }] };
  };
  const title = useAnimatedStyle(() => text(scrollX.get(), 0.15));
  const body = useAnimatedStyle(() => text(scrollX.get(), 0.3));
  const { main } = accentColors(colors, slide.accent);
  const first = index === 0;
  return <View style={[styles.slide, { width }]} accessible accessibilityLabel={`${slide.title}. ${slide.body}`}>
    <Animated.View entering={first ? ENTER_LEAD : undefined} style={[styles.stage, { height: stage + 24 }]}>
      <Animated.View style={art}>
        <slide.Illustration size={stage} active={active} reduced={reduced} colors={colors} />
      </Animated.View>
    </Animated.View>
    <View style={styles.copy}>
      <Animated.View entering={first ? ENTER_TITLE : undefined} style={title}>
        <Text style={[styles.slideTitle, { color: colors.text }]}>{slide.title}</Text>
        <View style={[styles.underline, { backgroundColor: main }]} />
      </Animated.View>
      <Animated.View entering={first ? ENTER_BODY : undefined} style={body}>
        <Text style={[styles.slideBody, { color: colors.textSecondary }]}>{slide.body}</Text>
      </Animated.View>
    </View>
  </View>;
}

/** Static dots plus one pill that tracks the scroll 1:1 and takes each slide's colour. */
function Dots({ scrollX, width, colors }: { scrollX: SharedValue<number>; width: number; colors: Palette }) {
  const STEP = DOT_STEP;
  const accents = SLIDES.map(s => accentColors(colors, s.accent).main);
  const inputs = SLIDES.map((_, i) => i * width);
  const pill = useAnimatedStyle(() => ({
    backgroundColor: interpolateColor(scrollX.get(), inputs, accents),
    transform: [{ translateX: interpolate(scrollX.get(), [0, LAST * width], [0, LAST * STEP], Extrapolation.CLAMP) }],
  }));
  return <View accessibilityElementsHidden importantForAccessibility="no-hide-descendants" style={styles.dots}>
    {SLIDES.map((s, i) => <View key={s.title} style={[styles.dot, { left: i * STEP, backgroundColor: colors.text, opacity: 0.16 }]} />)}
    <Animated.View style={[styles.pill, pill]} />
  </View>;
}

/** Two soft colour fields drifting with the swipe (decoration: tied to the finger, never looping). */
function Blobs({ scrollX, width, colors }: { scrollX: SharedValue<number>; width: number; colors: Palette }) {
  const accents = SLIDES.map(s => accentColors(colors, s.accent).main);
  const inputs = SLIDES.map((_, i) => i * width);
  const a = useAnimatedStyle(() => ({ backgroundColor: interpolateColor(scrollX.get(), inputs, accents), transform: [{ translateX: -scrollX.get() * 0.06 }] }));
  const b = useAnimatedStyle(() => ({ backgroundColor: interpolateColor(scrollX.get(), inputs, accents), transform: [{ translateX: scrollX.get() * 0.04 }] }));
  return <View pointerEvents="none" style={StyleSheet.absoluteFill}>
    <Animated.View style={[styles.blob, { width: width * 0.9, height: width * 0.9, top: -width * 0.35, right: -width * 0.35 }, a]} />
    <Animated.View style={[styles.blob, { width: width * 0.7, height: width * 0.7, bottom: width * 0.25, left: -width * 0.4 }, b]} />
  </View>;
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  topBar: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 20, minHeight: 52 },
  brand: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  logo: { width: 26, height: 26, borderRadius: 7, alignItems: 'center', justifyContent: 'center', transform: [{ rotateZ: '45deg' }] },
  logoInner: { width: 12, height: 12, borderRadius: 3 },
  wordmark: { fontFamily: Fonts.heading, fontSize: 17, letterSpacing: -0.3 },
  skip: { minHeight: 44, minWidth: 44, paddingHorizontal: 12, alignItems: 'center', justifyContent: 'center', borderRadius: Radius.pill },
  skipText: { fontFamily: Fonts.bodySemi, fontSize: 16 },
  slide: { flex: 1, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 28, gap: 20 },
  stage: { alignItems: 'center', justifyContent: 'center' },
  copy: { gap: 12, alignSelf: 'stretch', alignItems: 'center' },
  slideTitle: { fontFamily: Fonts.display, fontSize: 34, letterSpacing: -1, textAlign: 'center' },
  underline: { alignSelf: 'center', width: 36, height: 5, borderRadius: 3, marginTop: 8 },
  slideBody: { fontFamily: Fonts.body, fontSize: 18, lineHeight: 26, textAlign: 'center', maxWidth: 360 },
  controls: { paddingHorizontal: 20, gap: 12 },
  dots: { height: 10, width: (SLIDES.length - 1) * DOT_STEP + 8, alignSelf: 'center', marginBottom: 6 },
  dot: { position: 'absolute', top: 1, width: 8, height: 8, borderRadius: 4 },
  pill: { position: 'absolute', top: 0, left: -7, width: 22, height: 10, borderRadius: 5 },   // centred on its 8px dot
  blob: { position: 'absolute', borderRadius: 9999, opacity: 0.12 },
});
