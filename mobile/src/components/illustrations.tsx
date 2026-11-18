/**
 * Result illustrations, drawn with views in the brand palette (no third-party art, nothing to credit).
 * Each one lands with a short rise (lead of its group) and then idles gently: stars twinkle, leaves
 * sway. Loops are slow, small and stop entirely under reduced motion.
 * Decorative: hidden from screen readers; the headline next to them carries the meaning.
 */
import { LinearGradient } from 'expo-linear-gradient';
import { useEffect, type ReactNode } from 'react';
import { StyleSheet, View } from 'react-native';
import Animated, {
  Easing, interpolate, useAnimatedStyle, useReducedMotion, useSharedValue, withDelay, withRepeat, withSequence, withTiming,
  type SharedValue,
} from 'react-native-reanimated';

import { Icon } from '@/components/ui';
import { EASE_IN_OUT, EASE_OUT } from '@/constants/motion';

const land = () => {
  'worklet';
  const timing = { duration: 500, easing: EASE_OUT };
  return { initialValues: { opacity: 0, transform: [{ translateY: 16 }, { scale: 0.92 }] },
    animations: { opacity: withTiming(1, timing), transform: [{ translateY: withTiming(0, timing) }, { scale: withTiming(1, timing) }] } };
};

function useIdle(period: number, delay = 600): SharedValue<number> {
  const reduced = useReducedMotion();
  const t = useSharedValue(0);
  useEffect(() => {
    if (reduced) return;
    t.set(withDelay(delay, withRepeat(withSequence(
      withTiming(1, { duration: period / 2, easing: EASE_IN_OUT }), withTiming(0, { duration: period / 2, easing: EASE_IN_OUT })), -1)));
  }, [reduced, t, period, delay]);
  return t;
}

function Frame({ size, children, backdrop }: { size: number; children: ReactNode; backdrop: readonly [string, string] }) {
  return <Animated.View entering={land} accessibilityElementsHidden importantForAccessibility="no-hide-descendants"
    style={{ width: size, height: size, alignItems: 'center', justifyContent: 'center' }}>
    <LinearGradient colors={backdrop} start={{ x: 0.2, y: 0 }} end={{ x: 0.8, y: 1 }}
      style={{ position: 'absolute', width: size * 0.9, height: size * 0.9, borderRadius: size }} />
    {children}
  </Animated.View>;
}

function Twinkle({ t, phase, style, size, color }: { t: SharedValue<number>; phase: number; style: object; size: number; color: string }) {
  const s = useAnimatedStyle(() => {
    const v = (t.get() + phase) % 1;
    return { opacity: interpolate(v, [0, 0.5, 1], [0.35, 1, 0.35]), transform: [{ scale: interpolate(v, [0, 0.5, 1], [0.8, 1.1, 0.8]) }] };
  });
  return <Animated.View style={[styles.abs, style, s]}><Icon name={{ ios: 'sparkle', android: 'auto_awesome' }} size={size} color={color} /></Animated.View>;
}

/** A gold trophy on a plinth with twinkling stars: for a strong result. */
export function TrophyArt({ size = 160 }: { size?: number }) {
  const t = useIdle(2400);
  const u = size / 160;
  const bob = useAnimatedStyle(() => ({ transform: [{ translateY: interpolate(t.get(), [0, 1], [0, -4 * u]) }] }));
  return <Frame size={size} backdrop={['#fff1d6', '#dbf4e8']}>
    <Animated.View style={[{ alignItems: 'center' }, bob]}>
      <View style={{ flexDirection: 'row', alignItems: 'flex-start' }}>
        <View style={[styles.handle, { width: 26 * u, height: 30 * u, borderWidth: 6 * u, marginRight: -10 * u, marginTop: 6 * u }]} />
        <LinearGradient colors={['#ffd36b', '#f29d16']} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }}
          style={{ width: 66 * u, height: 58 * u, borderTopLeftRadius: 8 * u, borderTopRightRadius: 8 * u, borderBottomLeftRadius: 33 * u, borderBottomRightRadius: 33 * u, alignItems: 'center', justifyContent: 'center' }}>
          <View style={{ position: 'absolute', left: 10 * u, top: 8 * u, width: 9 * u, height: 26 * u, borderRadius: 5 * u, backgroundColor: 'rgba(255,255,255,0.45)' }} />
          <Icon name={{ ios: 'star.fill', android: 'star' }} size={22 * u} color="#ffffff" />
        </LinearGradient>
        <View style={[styles.handle, { width: 26 * u, height: 30 * u, borderWidth: 6 * u, marginLeft: -10 * u, marginTop: 6 * u }]} />
      </View>
      <View style={{ width: 12 * u, height: 14 * u, backgroundColor: '#e08a0e' }} />
      <View style={{ width: 44 * u, height: 8 * u, borderRadius: 4 * u, backgroundColor: '#f29d16' }} />
      <View style={{ width: 64 * u, height: 16 * u, borderRadius: 5 * u, backgroundColor: '#156b4d', marginTop: 2 * u }} />
    </Animated.View>
    <Twinkle t={t} phase={0} size={18 * u} color="#f29d16" style={{ top: 22 * u, left: 30 * u }} />
    <Twinkle t={t} phase={0.33} size={14 * u} color="#1fa774" style={{ top: 40 * u, right: 26 * u }} />
    <Twinkle t={t} phase={0.66} size={11 * u} color="#2f6fe4" style={{ bottom: 36 * u, left: 24 * u }} />
  </Frame>;
}

/** A sprouting plant in a pot: for "keep going". Its leaves sway a little. */
export function SproutArt({ size = 160 }: { size?: number }) {
  const t = useIdle(3200);
  const u = size / 160;
  const sway = useAnimatedStyle(() => ({ transform: [{ rotateZ: `${interpolate(t.get(), [0, 1], [-4, 4])}deg` }] }));
  const leaf = (flip: 1 | -1, scale: number) => ({
    width: 34 * u * scale, height: 18 * u * scale, backgroundColor: flip === 1 ? '#1fa774' : '#3fd29a',
    borderTopLeftRadius: flip === 1 ? 2 : 18 * u, borderBottomRightRadius: flip === 1 ? 2 : 18 * u,
    borderTopRightRadius: flip === 1 ? 18 * u : 2, borderBottomLeftRadius: flip === 1 ? 18 * u : 2,
  });
  return <Frame size={size} backdrop={['#dbf4e8', '#e3edff']}>
    <View style={{ alignItems: 'center', marginTop: 20 * u }}>
      <Animated.View style={[{ alignItems: 'center', transformOrigin: 'bottom' }, sway]}>
        <View style={{ flexDirection: 'row', alignItems: 'flex-end', marginBottom: -4 * u }}>
          <View style={[leaf(-1, 1), { transform: [{ rotateZ: '-28deg' }], marginRight: -2 * u }]} />
          <View style={[leaf(1, 1.15), { transform: [{ rotateZ: '24deg' }], marginLeft: -2 * u, marginBottom: 10 * u }]} />
        </View>
        <View style={{ width: 5 * u, height: 30 * u, borderRadius: 3 * u, backgroundColor: '#156b4d' }} />
      </Animated.View>
      <View style={{ width: 70 * u, height: 12 * u, borderRadius: 4 * u, backgroundColor: '#c63c2b' }} />
      <LinearGradient colors={['#f8624d', '#c63c2b']} style={{ width: 56 * u, height: 40 * u, borderBottomLeftRadius: 14 * u, borderBottomRightRadius: 14 * u }} />
    </View>
    <Twinkle t={t} phase={0} size={14 * u} color="#1fa774" style={{ top: 30 * u, right: 34 * u }} />
    <Twinkle t={t} phase={0.5} size={11 * u} color="#f29d16" style={{ top: 52 * u, left: 30 * u }} />
  </Frame>;
}

/** 24 dots in a ring that fill, one after another, to the result (an Apple-style dial). */
export function MasteryDial({ value, size = 112, color, track, children }: { value: number; size?: number; color: string; track: string; children?: ReactNode }) {
  const reduced = useReducedMotion();
  const progress = useSharedValue(reduced ? value : 0);
  useEffect(() => {
    progress.set(reduced ? value : withDelay(120, withTiming(value, { duration: 800, easing: Easing.bezier(0.23, 1, 0.32, 1) })));
  }, [value, reduced, progress]);
  const DOTS = 24;
  const radius = size / 2 - 7;
  return <View style={{ width: size, height: size, alignItems: 'center', justifyContent: 'center' }}>
    {Array.from({ length: DOTS }, (_, i) => {
      const angle = (i / DOTS) * Math.PI * 2 - Math.PI / 2;
      return <Dot key={i} index={i} count={DOTS} progress={progress} color={color} track={track}
        x={size / 2 + Math.cos(angle) * radius - 4} y={size / 2 + Math.sin(angle) * radius - 4} />;
    })}
    {children}
  </View>;
}

function Dot({ index, count, progress, color, track, x, y }: { index: number; count: number; progress: SharedValue<number>; color: string; track: string; x: number; y: number }) {
  const style = useAnimatedStyle(() => {
    const filled = progress.get() * count - index;           // >1 full, 0..1 filling, <0 empty
    const on = Math.min(1, Math.max(0, filled));
    return { opacity: 0.35 + 0.65 * on, transform: [{ scale: 0.75 + 0.35 * on }], backgroundColor: on > 0.5 ? color : track };
  });
  return <Animated.View style={[styles.dot, { left: x, top: y }, style]} />;
}

const styles = StyleSheet.create({
  abs: { position: 'absolute' },
  handle: { borderRadius: 999, borderColor: '#f2b13c', backgroundColor: 'transparent' },
  dot: { position: 'absolute', width: 8, height: 8, borderRadius: 4 },
});
