/**
 * A one-shot confetti burst for good results (rare tier: the delight budget lives here).
 * Pieces fly outward with their own spin and fade within 900ms, strong ease-out, on the UI
 * thread. Fires its success haptic in the same frame it starts, unless the action that led here
 * already gave one (one haptic per event). Skipped under reduced motion.
 * Decorative: the score text beside it carries the meaning.
 */
import { useEffect, useMemo } from 'react';
import { StyleSheet, View } from 'react-native';
import Animated, { interpolate, useAnimatedStyle, useReducedMotion, useSharedValue, withTiming, type SharedValue } from 'react-native-reanimated';

import { EASE_OUT } from '@/constants/motion';
import { useTheme } from '@/hooks/use-theme';
import { haptics } from '@/utils/haptics';

const PIECES = 16;

export function Celebration({ play, haptic = true }: { play: boolean; haptic?: boolean }) {
  const colors = useTheme();
  const reduced = useReducedMotion();
  const t = useSharedValue(0);
  const palette = [colors.blue, colors.amber, colors.green, colors.coral];
  // Deterministic spread: even angles with a fixed jitter, so every burst looks the same.
  const pieces = useMemo(() => Array.from({ length: PIECES }, (_, i) => ({
    angle: (i / PIECES) * Math.PI * 2 + (i % 3) * 0.17,
    distance: 90 + (i % 4) * 26,
    spin: (i % 2 ? 1 : -1) * (180 + (i % 5) * 70),
    color: palette[i % palette.length],
    wide: i % 3 === 0,
  // eslint-disable-next-line react-hooks/exhaustive-deps
  })), [colors]);

  useEffect(() => {
    if (!play) return;
    if (haptic) haptics.success();
    if (reduced) return;
    t.set(0);
    t.set(withTiming(1, { duration: 900, easing: EASE_OUT }));
  }, [play, reduced, t, haptic]);

  if (!play || reduced) return null;
  return <View pointerEvents="none" accessibilityElementsHidden importantForAccessibility="no-hide-descendants" style={styles.origin}>
    {pieces.map((p, i) => <Piece key={i} t={t} {...p} />)}
  </View>;
}

function Piece({ t, angle, distance, spin, color, wide }: { t: SharedValue<number>; angle: number; distance: number; spin: number; color: string; wide: boolean }) {
  const style = useAnimatedStyle(() => {
    const v = t.get();
    return {
      opacity: interpolate(v, [0, 0.1, 0.7, 1], [0, 1, 1, 0]),
      transform: [
        { translateX: Math.cos(angle) * distance * v },
        { translateY: Math.sin(angle) * distance * v + 40 * v * v },   // a little gravity at the end
        { rotateZ: `${spin * v}deg` },
        { scale: interpolate(v, [0, 0.15, 1], [0.6, 1, 0.9]) },
      ],
    };
  });
  return <Animated.View style={[styles.piece, wide ? styles.wide : styles.square, { backgroundColor: color }, style]} />;
}

const styles = StyleSheet.create({
  origin: { position: 'absolute', top: '40%', left: '50%', width: 0, height: 0, overflow: 'visible' },
  piece: { position: 'absolute', borderRadius: 2 },
  square: { width: 8, height: 8, left: -4, top: -4 },
  wide: { width: 12, height: 6, left: -6, top: -3 },
});
