/**
 * A deck of flashcards: flip the top card with a tap, throw it right for "Got it" and left for
 * "Still learning". The next two cards wait underneath.
 *
 * Motion (gestures + animate-expo + choreograph skills):
 *  - Flip: rotateY 0° → 180° with perspective, 300ms strong ease-in-out; the card lifts 6% at the
 *    halfway point so it reads as an object turning over, not a picture swapping.
 *  - Drag: while the finger is down the card IS the finger (1:1, from wherever it was caught, with a
 *    slight tilt). One value drives everything linked to it: the GOT IT / AGAIN stamps fade in by
 *    direction, and the cards underneath rise toward the top as it leaves.
 *  - Release: Apple's momentum projection decides (src/utils/swipe.ts). Commit flies the card off
 *    at the finger's speed (spring, damping 0.8, seeded with velocity); otherwise it springs home.
 *  - Buttons throw the card the same way (an exit layout animation toward the answer's side, 220ms,
 *    faster than the 200ms+ entrance of the next card so the response feels immediate).
 *  - Reduced motion: faces crossfade, nothing flies or tilts, cards simply change.
 */
import { useEffect, useState, type ReactNode } from 'react';
import { Pressable, StyleSheet, Text, useWindowDimensions, View } from 'react-native';
import { GestureDetector, usePanGesture } from 'react-native-gesture-handler';
import Animated, {
  cancelAnimation, Extrapolation, interpolate, useAnimatedStyle, useReducedMotion, useSharedValue, withSpring, withTiming,
  type SharedValue,
} from 'react-native-reanimated';
import { scheduleOnRN } from 'react-native-worklets';

import { EASE_IN_OUT, EASE_OUT, FLIP_MS, SPRING_RELEASE } from '@/constants/motion';
import { Fonts } from '@/constants/theme';
import { swipeOutcome } from '@/utils/swipe';

export interface DeckCard { id: string; front: string; back: string }
export type Answer = 'known' | 'learning';

const exitToward = (direction: 1 | -1) => () => {
  'worklet';
  const timing = { duration: 220, easing: EASE_OUT };
  return {
    initialValues: { opacity: 1, transform: [{ translateX: 0 }, { rotateZ: '0deg' }] },
    animations: { opacity: withTiming(0, timing),
      transform: [{ translateX: withTiming(direction * 420, timing) }, { rotateZ: withTiming(`${direction * 16}deg`, timing) }] },
  };
};
const settleIn = () => {
  'worklet';
  const timing = { duration: 200, easing: EASE_OUT };
  return { initialValues: { opacity: 0.6, transform: [{ translateY: 16 }, { scale: 0.94 }] },
    animations: { opacity: withTiming(1, timing), transform: [{ translateY: withTiming(0, timing) }, { scale: withTiming(1, timing) }] } };
};

export function CardDeck({ cards, flipped, onFlip, onAnswer, renderFront, renderBack, renderWaiting, height = 380, leaving }: {
  cards: DeckCard[]; flipped: boolean; onFlip: () => void; onAnswer: (answer: Answer) => void;
  renderFront: (card: DeckCard) => ReactNode; renderBack: (card: DeckCard) => ReactNode; height?: number;
  /** The face of a card waiting underneath (defaults to its front). */
  renderWaiting?: (card: DeckCard) => ReactNode;
  /** The side the current top card will leave on when a button answers it. */
  leaving?: Answer;
}) {
  const { width } = useWindowDimensions();
  const reduced = useReducedMotion();
  const x = useSharedValue(0);
  const grabbedAt = useSharedValue(0);
  const turn = useSharedValue(flipped ? 1 : 0);
  const [thrown, setThrown] = useState<1 | -1>(1);
  const top = cards[0];
  const direction: 1 | -1 = leaving ? (leaving === 'known' ? 1 : -1) : thrown;

  useEffect(() => {
    turn.set(reduced ? (flipped ? 1 : 0) : withTiming(flipped ? 1 : 0, { duration: FLIP_MS, easing: EASE_IN_OUT }));
  }, [flipped, reduced, turn]);
  useEffect(() => { x.set(0); }, [top?.id, x]);                 // a new top card starts centred

  const commit = (side: 1 | -1) => { setThrown(side); onAnswer(side === 1 ? 'known' : 'learning'); };

  const pan = usePanGesture({
    activeOffsetX: [-12, 12],
    failOffsetY: [-14, 14],                                     // vertical movement belongs to the page
    onActivate: () => { cancelAnimation(x); grabbedAt.set(x.get()); },
    onUpdate: e => { x.set(grabbedAt.get() + e.translationX); },
    onDeactivate: e => {
      const outcome = swipeOutcome(grabbedAt.get() + e.translationX, e.velocityX, width);
      if (outcome === 0) { x.set(withSpring(0, { ...SPRING_RELEASE, velocity: e.velocityX })); return; }
      const side = outcome === 1 ? 1 : -1;
      x.set(withSpring(side * width * 1.4, { ...SPRING_RELEASE, velocity: e.velocityX, overshootClamping: true }, done => {
        if (done) scheduleOnRN(commit, side);
      }));
    },
  });

  const topStyle = useAnimatedStyle(() => {
    const dx = x.get();
    const lift = interpolate(turn.get(), [0, 0.5, 1], [1, 1.06, 1]);
    return reduced
      ? { opacity: interpolate(Math.abs(dx), [0, width], [1, 0], Extrapolation.CLAMP) }
      : { transform: [{ translateX: dx }, { rotateZ: `${interpolate(dx, [-width, 0, width], [-16, 0, 16])}deg` }, { scale: lift }] };
  });
  const frontFace = useAnimatedStyle(() => reduced ? { opacity: 1 - turn.get() }
    : { transform: [{ perspective: 1200 }, { rotateY: `${turn.get() * 180}deg` }] });
  const backFace = useAnimatedStyle(() => reduced ? { opacity: turn.get() }
    : { transform: [{ perspective: 1200 }, { rotateY: `${turn.get() * 180 + 180}deg` }] });
  const knownStamp = useAnimatedStyle(() => ({ opacity: interpolate(x.get(), [20, 110], [0, 1], Extrapolation.CLAMP) }));
  const learningStamp = useAnimatedStyle(() => ({ opacity: interpolate(x.get(), [-110, -20], [1, 0], Extrapolation.CLAMP) }));

  if (!top) return null;
  return <View style={{ height: height + 52 }}>
    {cards.slice(1, 3).map((card, i) => ({ card, depth: i + 1 })).reverse().map(({ card, depth }) =>
      <Behind key={card.id} depth={depth} x={x} width={width} height={height} reduced={reduced}>{(renderWaiting ?? renderFront)(card)}</Behind>)}
    <Animated.View key={top.id} entering={reduced ? undefined : settleIn} exiting={reduced ? undefined : exitToward(direction)} style={[styles.slot, { height }]}>
      <GestureDetector gesture={pan}>
        <Animated.View style={[styles.fill, topStyle]}>
          <Pressable onPress={onFlip} accessibilityRole="button" style={styles.fill}
            accessibilityHint={`Double tap to show the ${flipped ? 'question' : 'answer'}. Swipe right if you knew it, left to keep learning it.`}>
            <Animated.View style={[styles.face, frontFace]} accessibilityElementsHidden={flipped} importantForAccessibility={flipped ? 'no-hide-descendants' : 'auto'}>
              {renderFront(top)}
            </Animated.View>
            <Animated.View style={[styles.face, backFace]} accessibilityElementsHidden={!flipped} importantForAccessibility={flipped ? 'auto' : 'no-hide-descendants'}>
              {renderBack(top)}
            </Animated.View>
          </Pressable>
          <Animated.View pointerEvents="none" accessibilityElementsHidden style={[styles.stamp, styles.stampKnown, knownStamp]}>
            <Text style={[styles.stampText, { color: '#16a06a' }]}>GOT IT</Text>
          </Animated.View>
          <Animated.View pointerEvents="none" accessibilityElementsHidden style={[styles.stamp, styles.stampLearning, learningStamp]}>
            <Text style={[styles.stampText, { color: '#e08a0e' }]}>AGAIN</Text>
          </Animated.View>
        </Animated.View>
      </GestureDetector>
    </Animated.View>
  </View>;
}

/** A waiting card: 5% smaller and 24pt lower per step back, so its edge shows; rises as the top card leaves. */
function Behind({ depth, x, width, height, reduced, children }: {
  depth: number; x: SharedValue<number>; width: number; height: number; reduced: boolean; children: ReactNode;
}) {
  const style = useAnimatedStyle(() => {
    const progress = reduced ? 0 : interpolate(Math.abs(x.get()), [0, width * 0.6], [0, 1], Extrapolation.CLAMP);
    const step = depth - progress;
    return { opacity: interpolate(step, [0, 1, 2], [1, 0.85, 0.6]), transform: [{ translateY: step * 24 }, { scale: 1 - step * 0.05 }] };
  });
  return <Animated.View pointerEvents="none" accessibilityElementsHidden importantForAccessibility="no-hide-descendants"
    style={[styles.slot, { height }, style]}>{children}</Animated.View>;
}

const styles = StyleSheet.create({
  slot: { position: 'absolute', left: 0, right: 0, top: 0 },
  fill: { flex: 1 },
  face: { position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, backfaceVisibility: 'hidden' },
  stamp: { position: 'absolute', top: 30, paddingHorizontal: 12, paddingVertical: 4, borderWidth: 3, borderRadius: 10, backgroundColor: 'rgba(255,255,255,0.94)' },
  stampKnown: { left: 22, borderColor: '#16a06a', transform: [{ rotateZ: '-14deg' }] },
  stampLearning: { right: 22, borderColor: '#e08a0e', transform: [{ rotateZ: '14deg' }] },
  stampText: { fontFamily: Fonts.display, fontSize: 24, letterSpacing: 1 },
});
