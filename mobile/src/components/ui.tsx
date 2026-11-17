import { type ReactNode } from 'react';
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, TextInput, View, type TextInputProps } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { MaxContentWidth, Spacing, TouchTarget } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';

export function Screen({ children, scroll = true }: { children: ReactNode; scroll?: boolean }) {
  const colors = useTheme();
  const insets = useSafeAreaInsets();
  const body = <View style={[styles.content, { paddingTop: insets.top + Spacing.three }]}>{children}</View>;
  return <View style={[styles.flex, { backgroundColor: colors.background }]}>
    {scroll ? <ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={{ paddingBottom: insets.bottom + 96 }}>{body}</ScrollView> : body}
  </View>;
}

export function Heading({ children, level = 1 }: { children: ReactNode; level?: 1 | 2 }) {
  const colors = useTheme();
  return <Text accessibilityRole="header" style={[level === 1 ? styles.h1 : styles.h2, { color: colors.text }]}>{children}</Text>;
}

export function Body({ children, muted }: { children: ReactNode; muted?: boolean }) {
  const colors = useTheme();
  return <Text style={[styles.body, { color: muted ? colors.textSecondary : colors.text }]}>{children}</Text>;
}

export function Card({ children }: { children: ReactNode }) {
  const colors = useTheme();
  return <View style={[styles.card, { backgroundColor: colors.backgroundElement, borderColor: colors.border }]}>{children}</View>;
}

type Variant = 'primary' | 'secondary' | 'danger';

export function Button({ label, onPress, variant = 'primary', disabled, busy }: {
  label: string; onPress: () => void; variant?: Variant; disabled?: boolean; busy?: boolean;
}) {
  const colors = useTheme();
  const background = variant === 'primary' ? colors.tint : 'transparent';
  const foreground = variant === 'primary' ? colors.onTint : variant === 'danger' ? colors.danger : colors.text;
  const border = variant === 'danger' ? colors.danger : variant === 'primary' ? colors.tint : colors.border;
  return <Pressable accessibilityRole="button" accessibilityLabel={label} accessibilityState={{ disabled: !!disabled || !!busy, busy: !!busy }}
    disabled={disabled || busy} onPress={onPress}
    style={({ pressed }) => [styles.button, { backgroundColor: background, borderColor: border, opacity: disabled ? 0.5 : pressed ? 0.8 : 1 }]}>
    {busy ? <ActivityIndicator color={foreground} /> : <Text style={[styles.buttonText, { color: foreground }]}>{label}</Text>}
  </Pressable>;
}

export function Field({ label, ...props }: TextInputProps & { label: string }) {
  const colors = useTheme();
  return <View style={styles.field}>
    <Text style={[styles.label, { color: colors.textSecondary }]}>{label}</Text>
    <TextInput accessibilityLabel={label} placeholderTextColor={colors.textSecondary} {...props}
      style={[styles.input, { color: colors.text, borderColor: colors.border, backgroundColor: colors.background }, props.style]} />
  </View>;
}

/** Status messages are announced; errors use the alert role so screen readers read them at once. */
export function Notice({ text, kind = 'status' }: { text: string; kind?: 'status' | 'error' }) {
  const colors = useTheme();
  if (!text) return null;
  return <Text accessibilityRole={kind === 'error' ? 'alert' : 'text'} accessibilityLiveRegion="polite"
    style={[styles.body, { color: kind === 'error' ? colors.danger : colors.success }]}>{text}</Text>;
}

export function Segmented<T extends string>({ options, value, onChange }: { options: { value: T; label: string }[]; value: T; onChange: (v: T) => void }) {
  const colors = useTheme();
  return <View accessibilityRole="tablist" style={[styles.segmented, { borderColor: colors.border }]}>
    {options.map(o => <Pressable key={o.value} accessibilityRole="tab" accessibilityState={{ selected: o.value === value }} onPress={() => onChange(o.value)}
      style={[styles.segment, o.value === value && { backgroundColor: colors.backgroundSelected }]}>
      <Text style={{ color: colors.text, fontWeight: o.value === value ? '700' : '500' }}>{o.label}</Text>
    </Pressable>)}
  </View>;
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  content: { width: '100%', maxWidth: MaxContentWidth, alignSelf: 'center', paddingHorizontal: Spacing.three, gap: Spacing.three },
  h1: { fontSize: 28, fontWeight: '700' },
  h2: { fontSize: 19, fontWeight: '700' },
  body: { fontSize: 16, lineHeight: 23 },
  card: { borderWidth: StyleSheet.hairlineWidth, borderRadius: 14, padding: Spacing.three, gap: Spacing.two },
  button: { minHeight: TouchTarget, borderRadius: 12, borderWidth: 1, paddingHorizontal: Spacing.three, alignItems: 'center', justifyContent: 'center' },
  buttonText: { fontSize: 16, fontWeight: '600' },
  field: { gap: Spacing.one },
  label: { fontSize: 14 },
  input: { minHeight: TouchTarget, borderWidth: 1, borderRadius: 10, paddingHorizontal: Spacing.three, fontSize: 16 },
  segmented: { flexDirection: 'row', borderWidth: 1, borderRadius: 12, overflow: 'hidden' },
  segment: { flex: 1, minHeight: TouchTarget, alignItems: 'center', justifyContent: 'center' },
});
