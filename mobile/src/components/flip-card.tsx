/**
 * A flashcard you flip with a tap and throw with a swipe.
 *
 *  - Flip: rotateY 0° → 180° with perspective, 300ms strong ease-in-out (on-screen movement; used
 *    dozens of times a session, so it stays inside the 300ms UI budget).
 *    Both faces are drawn; the one facing away is hidden from screen readers.
 *  - Swipe (gestures skill): while the finger is down the card IS the finger (1:1, a slight tilt,
 *    no easing). On release, Apple's momentum projection decides: a flick commits even over a
 *    short distance, a slow drag past 40% of the width commits, anything else springs home
 *    (400ms, damping 0.8, seeded with the release velocity). A committed card leaves at the
 *    finger's speed, one light haptic marks the commit, and the next card settles in.
 *  - Reduced motion: faces crossfade instead of turning, and a committed card just fades.
 */
import { useEffect, type ReactNode } from 'react';
import { Pressable, StyleSheet, useWindowDimensions } from 'react-native';
import { GestureDetector, usePanGesture } from 'react-native-gesture-handler';
import Animated, { cancelAnimation, interpolate, useAnimatedStyle, useReducedMotion, useSharedValue, withSpring, withTiming } from 'react-native-reanimated';
import { scheduleOnRN } from 'react-native-worklets';

import { EASE_IN_OUT, FLIP_MS, SPRING_RELEASE } from '@/constants/motion';
import { haptics } from '@/utils/haptics';
import { swipeOutcome } from '@/utils/swipe';

export function FlipCard({ front, back, flipped, onFlip, onSwipe, height = 300 }: {
  front: ReactNode; back: ReactNode; flipped: boolean; onFlip: () => void; onSwipe: (direction: -1 | 1) => void; height?: number;
}) {
  const { width } = useWindowDimensions();
  const reduced = useReducedMotion();
  const turn = useSharedValue(flipped ? 1 : 0);
  const x = useSharedValue(0);
  const grabbedAt = useSharedValue(0);

  useEffect(() => {
    turn.set(reduced ? (flipped ? 1 : 0) : withTiming(flipped ? 1 : 0, { duration: FLIP_MS, easing: EASE_IN_OUT }));
  }, [flipped, reduced, turn]);

  const commit = (direction: -1 | 1) => { haptics.snap(); onSwipe(direction); };

  const pan = usePanGesture({
    activeOffsetX: [-12, 12],
    failOffsetY: [-14, 14],                        // vertical movement belongs to the page scroll
    // Catching a card mid-throw keeps it where it is: track from the grab point, not from centre.
    onActivate: () => { cancelAnimation(x); grabbedAt.set(x.get()); },
    onUpdate: e => { x.set(grabbedAt.get() + e.translationX); },
    onDeactivate: e => {
      const outcome = swipeOutcome(grabbedAt.get() + e.translationX, e.velocityX, width);
      if (outcome === 0) { x.set(withSpring(0, { ...SPRING_RELEASE, velocity: e.velocityX })); return; }
      const leave = outcome * width * 1.3;
      x.set(withSpring(leave, { ...SPRING_RELEASE, velocity: e.velocityX, overshootClamping: true }, done => {
        if (done) scheduleOnRN(commit, outcome === -1 ? -1 : 1);
      }));
    },
  });

  // A new card (after a commit) starts centred: reset the throw.
  useEffect(() => { x.set(0); }, [front, x]);

  const card = useAnimatedStyle(() => {
    const dx = x.get();
    return {
      opacity: reduced ? interpolate(Math.abs(dx), [0, width], [1, 0]) : 1,
      transform: [{ translateX: reduced ? 0 : dx }, { rotateZ: `${interpolate(dx, [-width, 0, width], [-14, 0, 14])}deg` }],
    };
  });
  const frontFace = useAnimatedStyle(() => reduced
    ? { opacity: 1 - turn.get() }
    : { transform: [{ perspective: 1200 }, { rotateY: `${turn.get() * 180}deg` }] });
  const backFace = useAnimatedStyle(() => reduced
    ? { opacity: turn.get() }
    : { transform: [{ perspective: 1200 }, { rotateY: `${turn.get() * 180 + 180}deg` }] });

  return <GestureDetector gesture={pan}>
    <Animated.View style={[{ height }, card]}>
      <Pressable onPress={onFlip} accessibilityRole="button"
        accessibilityHint={`Double tap to show the ${flipped ? 'question' : 'answer'}. Swipe left for the next card, right for the previous one.`} style={styles.fill}>
        <Animated.View style={[styles.face, frontFace]} accessibilityElementsHidden={flipped} importantForAccessibility={flipped ? 'no-hide-descendants' : 'auto'}>
          {front}
        </Animated.View>
        <Animated.View style={[styles.face, backFace]} accessibilityElementsHidden={!flipped} importantForAccessibility={flipped ? 'auto' : 'no-hide-descendants'}>
          {back}
        </Animated.View>
      </Pressable>
    </Animated.View>
  </GestureDetector>;
}

const styles = StyleSheet.create({
  fill: { flex: 1 },
  face: { position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, backfaceVisibility: 'hidden' },
});

