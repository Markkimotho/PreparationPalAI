/**
 * The app's building blocks. Motion rules (animate-expo skill): press feedback is a 120ms scale to
 * 0.97 via a Reanimated CSS transition; indicators move on the UI thread with a strong ease-in-out;
 * nothing animates layout properties except childless, absolutely positioned fills.
 */
import { LinearGradient } from 'expo-linear-gradient';
import { SymbolView, type SymbolViewProps } from 'expo-symbols';
import { useEffect, useState, type ComponentRef, type ReactNode, type Ref } from 'react';
import {
  ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, TextInput, View,
  type LayoutChangeEvent, type StyleProp, type TextInputProps, type ViewStyle,
} from 'react-native';
import Animated, { useAnimatedStyle, useReducedMotion, useSharedValue, withTiming } from 'react-native-reanimated';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { EASE_IN_OUT, EASE_OUT, EASE_OUT_CSS, PRESS_MS, SMALL_STATE_MS } from '@/constants/motion';
import { accentColors, Fonts, MaxContentWidth, Radius, Spacing, TouchTarget, type Accent } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import { haptics } from '@/utils/haptics';

/** An SF Symbol on iOS, a Material Symbol on Android. */
export type IconName = { ios: SymbolViewProps['name'] & string; android: string };

export function Icon({ name, size = 20, color }: { name: IconName; size?: number; color: string }) {
  return <SymbolView name={{ ios: name.ios, android: name.android } as SymbolViewProps['name']} size={size} tintColor={color}
    weight="semibold" style={{ width: size, height: size }} />;
}

/** Feedback on press-in (scale 0.97, 120ms), commit on press-out. */
export function PressableScale({ children, onPress, disabled, style, accessibilityLabel, accessibilityRole = 'button', accessibilityState, accessibilityHint }: {
  children: ReactNode; onPress?: () => void; disabled?: boolean; style?: StyleProp<ViewStyle>;
  accessibilityLabel?: string; accessibilityRole?: 'button' | 'tab' | 'link'; accessibilityHint?: string;
  accessibilityState?: { disabled?: boolean; selected?: boolean; busy?: boolean };
}) {
  const [pressed, setPressed] = useState(false);
  return <Pressable onPress={onPress} disabled={disabled} onPressIn={() => setPressed(true)} onPressOut={() => setPressed(false)}
    hitSlop={8} pressRetentionOffset={16} accessibilityRole={accessibilityRole} accessibilityLabel={accessibilityLabel}
    accessibilityHint={accessibilityHint} accessibilityState={{ disabled: !!disabled, ...accessibilityState }}>
    <Animated.View style={[PRESS_TRANSITION, pressed && !disabled && styles.pressed, style]}>{children}</Animated.View>
  </Pressable>;
}

export function Screen({ children, title, subtitle, eyebrow, accent = 'blue', right, scroll = true, scrollRef, onContentSizeChange }: {
  children: ReactNode; title?: string; subtitle?: string; eyebrow?: ReactNode; accent?: Accent; right?: ReactNode; scroll?: boolean;
  scrollRef?: Ref<ComponentRef<typeof ScrollView>>; onContentSizeChange?: () => void;
}) {
  const colors = useTheme();
  const insets = useSafeAreaInsets();
  const { soft } = accentColors(colors, accent);
  const header = title ? <View style={styles.header}>
    <View style={styles.headerText}>
      {eyebrow}
      <Text accessibilityRole="header" style={[styles.title, { color: colors.text }]}>{title}</Text>
      {subtitle ? <Text style={[styles.subtitle, { color: colors.textSecondary }]}>{subtitle}</Text> : null}
    </View>
    {right}
  </View> : null;
  const body = <View style={[styles.content, { paddingTop: insets.top + Spacing.three }]}>{header}{children}</View>;
  return <View style={[styles.flex, { backgroundColor: colors.background }]}>
    <LinearGradient pointerEvents="none" colors={[soft, colors.background]} style={[styles.wash, { height: insets.top + 280 }]} />
    {scroll ? <ScrollView ref={scrollRef} keyboardShouldPersistTaps="handled" keyboardDismissMode="interactive" onContentSizeChange={onContentSizeChange}
      contentContainerStyle={{ paddingBottom: insets.bottom + 110 }}>{body}</ScrollView> : body}
  </View>;
}

export function Heading({ children, level = 1 }: { children: ReactNode; level?: 1 | 2 | 3 }) {
  const colors = useTheme();
  return <Text accessibilityRole="header" style={[level === 1 ? styles.h1 : level === 2 ? styles.h2 : styles.h3, { color: colors.text }]}>{children}</Text>;
}

export function Body({ children, muted, center }: { children: ReactNode; muted?: boolean; center?: boolean }) {
  const colors = useTheme();
  return <Text style={[styles.body, { color: muted ? colors.textSecondary : colors.text }, center && styles.center]}>{children}</Text>;
}

export function Card({ children, style, tone = 'surface', accent = 'blue' }: {
  children: ReactNode; style?: StyleProp<ViewStyle>; tone?: 'surface' | 'soft'; accent?: Accent;
}) {
  const colors = useTheme();
  const background = tone === 'soft' ? accentColors(colors, accent).soft : colors.surface;
  return <View style={[styles.card, { backgroundColor: background, borderColor: colors.border, shadowColor: colors.shadow }, style]}>{children}</View>;
}

export function Pill({ label, icon, accent = 'blue' }: { label: string; icon?: IconName; accent?: Accent }) {
  const colors = useTheme();
  const { main, soft } = accentColors(colors, accent);
  return <View style={[styles.pill, { backgroundColor: soft }]}>
    {icon && <Icon name={icon} size={14} color={main} />}
    <Text style={[styles.pillText, { color: main }]}>{label}</Text>
  </View>;
}

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger';

export function Button({ label, onPress, variant = 'primary', accent = 'blue', icon, disabled, busy, compact }: {
  label: string; onPress: () => void; variant?: Variant; accent?: Accent; icon?: IconName; disabled?: boolean; busy?: boolean; compact?: boolean;
}) {
  const colors = useTheme();
  const { main, deep, soft } = accentColors(colors, accent);
  const foreground = variant === 'primary' ? '#ffffff' : variant === 'danger' ? colors.danger : variant === 'ghost' ? colors.text : main;
  const inner = busy ? <ActivityIndicator color={foreground} /> : <>
    {icon && <Icon name={icon} size={18} color={foreground} />}
    <Text style={[styles.buttonText, { color: foreground }]}>{label}</Text>
  </>;
  const shape = [styles.button, compact && styles.buttonCompact];
  return <PressableScale onPress={onPress} disabled={disabled || busy} accessibilityLabel={label} accessibilityState={{ busy: !!busy }}
    style={(disabled || busy) && variant === 'primary' ? styles.dimmed : disabled ? styles.dimmed : undefined}>
    {variant === 'primary'
      // The shadow sits on a solid layer under the gradient so iOS can rasterise it cheaply.
      ? <View style={[styles.primaryShadow, { shadowColor: deep, backgroundColor: deep, borderRadius: Radius.md }]}>
        <LinearGradient colors={[main, deep]} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={shape}>{inner}</LinearGradient>
      </View>
      : <View style={[shape, { backgroundColor: variant === 'secondary' ? soft : variant === 'danger' ? colors.dangerSoft : 'transparent' }]}>{inner}</View>}
  </PressableScale>;
}

export function Field({ label, hideLabel, accent = 'blue', ...props }: TextInputProps & { label: string; hideLabel?: boolean; accent?: Accent }) {
  const colors = useTheme();
  const [focused, setFocused] = useState(false);
  return <View style={styles.field}>
    {!hideLabel && <Text style={[styles.label, { color: colors.textSecondary }]}>{label}</Text>}
    <TextInput accessibilityLabel={label} placeholderTextColor={colors.textFaint} {...props}
      onFocus={e => { setFocused(true); props.onFocus?.(e); }} onBlur={e => { setFocused(false); props.onBlur?.(e); }}
      style={[styles.input, { color: colors.text, backgroundColor: colors.surface,
        borderColor: focused ? accentColors(colors, accent).main : colors.border }, props.style]} />
  </View>;
}

/** Status messages are announced; errors use the alert role so screen readers read them at once. */
export function Notice({ text, kind = 'status' }: { text: string; kind?: 'status' | 'error' }) {
  const colors = useTheme();
  if (!text) return null;
  const error = kind === 'error';
  const color = error ? colors.danger : colors.success;
  return <View accessible accessibilityRole={error ? 'alert' : 'text'} accessibilityLiveRegion="polite"
    style={[styles.notice, { backgroundColor: error ? colors.dangerSoft : colors.successSoft }]}>
    <Icon name={error ? { ios: 'exclamationmark.circle.fill', android: 'error' } : { ios: 'checkmark.circle.fill', android: 'check_circle' }} size={18} color={color} />
    <Text style={[styles.noticeText, { color: colors.text }]}>{text}</Text>
  </View>;
}

/** A segmented control whose selection pill slides between options (state indication, 180ms, UI thread). */
export function Segmented<T extends string>({ options, value, onChange, accent = 'blue' }: {
  options: { value: T; label: string; icon?: IconName }[]; value: T; onChange: (v: T) => void; accent?: Accent;
}) {
  const colors = useTheme();
  const reduced = useReducedMotion();
  const [width, setWidth] = useState(0);
  const index = Math.max(0, options.findIndex(o => o.value === value));
  const segment = width > 0 ? (width - 8) / options.length : 0;
  const x = useSharedValue(0);
  useEffect(() => {
    x.set(reduced || segment === 0 ? index * segment : withTiming(index * segment, { duration: SMALL_STATE_MS, easing: EASE_IN_OUT }));
  }, [index, segment, reduced, x]);
  const indicator = useAnimatedStyle(() => ({ transform: [{ translateX: x.get() }] }));
  const { main } = accentColors(colors, accent);
  return <View accessibilityRole="tablist" onLayout={(e: LayoutChangeEvent) => setWidth(e.nativeEvent.layout.width)}
    style={[styles.segmented, { backgroundColor: colors.backgroundElement }]}>
    {segment > 0 && <Animated.View pointerEvents="none" style={[styles.indicator, { width: segment, backgroundColor: colors.surface, shadowColor: colors.shadow }, indicator]} />}
    {options.map(o => {
      const selected = o.value === value;
      return <Pressable key={o.value} accessibilityRole="tab" accessibilityLabel={o.label} accessibilityState={{ selected }}
        onPress={() => { if (!selected) { haptics.select(); onChange(o.value); } }} style={styles.segment}>
        {o.icon && <Icon name={o.icon} size={15} color={selected ? main : colors.textSecondary} />}
        <Text style={[styles.segmentText, { color: selected ? colors.text : colors.textSecondary, fontFamily: selected ? Fonts.bodyBold : Fonts.bodySemi }]}>{o.label}</Text>
      </Pressable>;
    })}
  </View>;
}

export type OptionState = 'idle' | 'correct' | 'wrong' | 'dim';

/** A multiple-choice answer. Colour, icon and text all say whether it was right (never colour alone). */
export function OptionButton({ letter, text, state = 'idle', onPress, disabled, accent = 'amber' }: {
  letter: string; text: string; state?: OptionState; onPress: () => void; disabled?: boolean; accent?: Accent;
}) {
  const colors = useTheme();
  const { main, soft } = accentColors(colors, accent);
  const tone = state === 'correct' ? { bg: colors.successSoft, fg: colors.success } : state === 'wrong' ? { bg: colors.dangerSoft, fg: colors.danger } : { bg: colors.surface, fg: main };
  return <PressableScale onPress={onPress} disabled={disabled} accessibilityLabel={`${letter}. ${text}`}
    accessibilityHint={state === 'correct' ? 'Correct answer' : state === 'wrong' ? 'Your answer, incorrect' : undefined}
    style={[styles.option, { backgroundColor: tone.bg, borderColor: state === 'idle' || state === 'dim' ? colors.border : tone.fg }, state === 'dim' && styles.faded]}>
    <View style={[styles.letter, { backgroundColor: state === 'idle' || state === 'dim' ? soft : tone.fg }]}>
      {state === 'correct' || state === 'wrong'
        ? <Icon name={state === 'correct' ? { ios: 'checkmark', android: 'check' } : { ios: 'xmark', android: 'close' }} size={14} color="#ffffff" />
        : <Text style={[styles.letterText, { color: main }]}>{letter}</Text>}
    </View>
    <Text style={[styles.optionText, { color: colors.text }]}>{text}</Text>
  </PressableScale>;
}

/** A progress fill: absolutely positioned and childless, so animating its width re-lays-out nothing else. */
export function ProgressBar({ value, accent = 'blue', label }: { value: number; accent?: Accent; label?: string }) {
  const colors = useTheme();
  const reduced = useReducedMotion();
  const [track, setTrack] = useState(0);
  const width = useSharedValue(0);
  const target = track * Math.min(1, Math.max(0, value));
  useEffect(() => { width.set(reduced ? target : withTiming(target, { duration: 300, easing: EASE_OUT })); }, [target, reduced, width]);
  const fill = useAnimatedStyle(() => ({ width: width.get() }));
  return <View accessibilityRole="progressbar" accessibilityLabel={label} accessibilityValue={{ min: 0, max: 100, now: Math.round(value * 100) }}
    onLayout={e => setTrack(e.nativeEvent.layout.width)} style={[styles.track, { backgroundColor: colors.backgroundElement }]}>
    <Animated.View style={[styles.fill, { backgroundColor: accentColors(colors, accent).main }, fill]} />
  </View>;
}

/** Reanimated CSS transition: not a StyleSheet property, so it lives outside StyleSheet.create. */
// Colour changes (an answer turning right or wrong) ride the same 120ms transition: state, not a snap.
const PRESS_TRANSITION = {
  transform: [{ scale: 1 }], transitionProperty: ['transform', 'backgroundColor', 'borderColor'] as ('transform' | 'backgroundColor' | 'borderColor')[],
  transitionDuration: PRESS_MS, transitionTimingFunction: EASE_OUT_CSS,
};

const styles = StyleSheet.create({
  flex: { flex: 1 },
  wash: { position: 'absolute', top: 0, left: 0, right: 0 },
  content: { width: '100%', maxWidth: MaxContentWidth, alignSelf: 'center', paddingHorizontal: 20, gap: Spacing.three },
  header: { flexDirection: 'row', alignItems: 'flex-end', gap: Spacing.three, marginBottom: Spacing.one },
  headerText: { flex: 1, gap: 6 },
  title: { fontFamily: Fonts.display, fontSize: 34, letterSpacing: -0.8 },
  subtitle: { fontFamily: Fonts.body, fontSize: 17, lineHeight: 23 },
  h1: { fontFamily: Fonts.display, fontSize: 28, letterSpacing: -0.5 },
  h2: { fontFamily: Fonts.heading, fontSize: 19, lineHeight: 25, letterSpacing: -0.2 },
  h3: { fontFamily: Fonts.headingSemi, fontSize: 16, lineHeight: 21 },
  body: { fontFamily: Fonts.body, fontSize: 17, lineHeight: 24 },
  center: { textAlign: 'center' },
  card: {
    borderRadius: Radius.lg, padding: 18, gap: Spacing.two, borderWidth: StyleSheet.hairlineWidth,
    shadowOpacity: 0.06, shadowRadius: 16, shadowOffset: { width: 0, height: 6 }, elevation: 2,
  },
  pressed: { transform: [{ scale: 0.97 }] },
  dimmed: { opacity: 0.45 },
  faded: { opacity: 0.55 },
  pill: { flexDirection: 'row', alignItems: 'center', gap: 5, alignSelf: 'flex-start', paddingHorizontal: 10, paddingVertical: 5, borderRadius: Radius.pill },
  pillText: { fontFamily: Fonts.bodyBold, fontSize: 13 },
  button: { minHeight: 54, borderRadius: Radius.md, paddingHorizontal: 20, flexDirection: 'row', gap: 8, alignItems: 'center', justifyContent: 'center' },
  buttonCompact: { minHeight: TouchTarget },
  primaryShadow: { shadowOpacity: 0.3, shadowRadius: 12, shadowOffset: { width: 0, height: 6 }, elevation: 3 },
  buttonText: { fontFamily: Fonts.heading, fontSize: 16, letterSpacing: -0.1 },
  field: { gap: 6 },
  label: { fontFamily: Fonts.bodySemi, fontSize: 15 },
  input: { minHeight: 52, borderWidth: 1.5, borderRadius: Radius.md, paddingHorizontal: Spacing.three, paddingVertical: 12, fontFamily: Fonts.body, fontSize: 17 },
  notice: { flexDirection: 'row', gap: 10, alignItems: 'flex-start', padding: 14, borderRadius: Radius.md },
  noticeText: { flex: 1, fontFamily: Fonts.body, fontSize: 16, lineHeight: 22 },
  segmented: { flexDirection: 'row', borderRadius: Radius.md, padding: 4 },
  indicator: { position: 'absolute', top: 4, bottom: 4, left: 4, borderRadius: 11, shadowOpacity: 0.08, shadowRadius: 6, shadowOffset: { width: 0, height: 2 }, elevation: 1 },
  segment: { flex: 1, minHeight: TouchTarget, flexDirection: 'row', gap: 6, alignItems: 'center', justifyContent: 'center' },
  segmentText: { fontSize: 15 },
  option: { flexDirection: 'row', alignItems: 'center', gap: 12, minHeight: 54, paddingHorizontal: 12, paddingVertical: 10, borderRadius: Radius.md, borderWidth: 1.5 },
  letter: { width: 30, height: 30, borderRadius: 15, alignItems: 'center', justifyContent: 'center' },
  letterText: { fontFamily: Fonts.heading, fontSize: 14 },
  optionText: { flex: 1, fontFamily: Fonts.body, fontSize: 17, lineHeight: 22 },
  track: { height: 8, borderRadius: 4, overflow: 'hidden' },
  fill: { position: 'absolute', left: 0, top: 0, bottom: 0, borderRadius: 4 },
});
