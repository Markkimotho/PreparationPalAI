/**
 * "Make it yours": the first thing a new learner sees after signing in, and the profile editor.
 *
 * Five short steps: name, goal, subjects and level, daily goal, look (accent colour and avatar).
 * Choreography: one step at a time; forward enters from the right and back from the left
 * (240ms strong ease-out), the old step leaves faster (160ms) while the new one arrives, and the
 * screen's colour follows the accent the learner picks. Shuffling the avatar flips it in 3D.
 * Reduced motion: steps crossfade, the avatar changes without turning.
 */
import { LinearGradient } from 'expo-linear-gradient';
import { router } from 'expo-router';
import { useEffect, useMemo, useState } from 'react';
import { ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import Animated, { FadeOut, useAnimatedStyle, useReducedMotion, useSharedValue, withSequence, withTiming } from 'react-native-reanimated';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { Avatar } from '@/components/avatar';
import { Button, Field, Icon, Notice, PressableScale, ProgressBar, Segmented, type IconName } from '@/components/ui';
import { EASE_IN_OUT, EASE_OUT } from '@/constants/motion';
import { accentColors, Fonts, Radius, type Accent } from '@/constants/theme';
import { useProfile, type Profile } from '@/hooks/use-profile';
import { useTheme } from '@/hooks/use-theme';
import { newSeed } from '@/utils/avatar';
import { haptics } from '@/utils/haptics';

export const POPULAR_SUBJECTS = ['Biology', 'Chemistry', 'Physics', 'Mathematics', 'Computer science', 'Economics',
  'Business', 'History', 'Medicine', 'Law', 'English', 'Engineering'];
const GOALS: { value: Profile['goal']; title: string; detail: string; icon: IconName }[] = [
  { value: 'exam', title: 'Ace an exam', detail: 'Recall, exam-style questions and timing.', icon: { ios: 'graduationcap.fill', android: 'school' } },
  { value: 'interview', title: 'Nail interviews', detail: 'Explain clearly and handle follow-ups.', icon: { ios: 'person.2.fill', android: 'groups' } },
  { value: 'understand', title: 'Understand deeply', detail: 'Intuition first, then the detail.', icon: { ios: 'lightbulb.fill', android: 'lightbulb' } },
];
const PACES = [
  { value: 5, title: 'Light', detail: 'A few minutes' }, { value: 10, title: 'Steady', detail: 'About ten minutes' },
  { value: 20, title: 'Focused', detail: 'A proper session' }, { value: 40, title: 'Intense', detail: 'Exam season' },
];
const ACCENTS: Accent[] = ['blue', 'amber', 'green', 'coral'];
const STEPS = 5;

const enterFrom = (side: 1 | -1) => () => {
  'worklet';
  const timing = { duration: 240, easing: EASE_OUT };
  return { initialValues: { opacity: 0, transform: [{ translateX: side * 28 }] },
    animations: { opacity: withTiming(1, timing), transform: [{ translateX: withTiming(0, timing) }] } };
};
const LEAVE = FadeOut.duration(160);

export function Setup({ editing = false }: { editing?: boolean }) {
  const colors = useTheme();
  const insets = useSafeAreaInsets();
  const reduced = useReducedMotion();
  const { profile, workspace, save } = useProfile();
  const [draft, setDraft] = useState<Profile>(() => ({ ...profile, avatar_seed: profile.avatar_seed || newSeed() }));
  const [step, setStep] = useState(0);
  const [direction, setDirection] = useState<1 | -1>(1);
  const [custom, setCustom] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const accent = accentColors(colors, draft.accent);
  const set = (changes: Partial<Profile>) => setDraft(d => ({ ...d, ...changes }));

  // First-time setup leaves for the app as soon as the profile is set up: when the learner finishes,
  // and also if the server says it already was (set up on another device).
  useEffect(() => { if (!editing && profile.onboarded) router.replace('/'); }, [editing, profile.onboarded]);

  const go = (to: number) => { setDirection(to > step ? 1 : -1); setStep(to); haptics.select(); };
  const finish = async (asIs = false) => {
    setBusy(true); setError('');
    try {
      await save({ ...(asIs ? profile : draft), avatar_seed: draft.avatar_seed, onboarded: true });
      haptics.success();
      if (editing) router.back();                    // first-time setup leaves through the effect above
    } catch (e) {
      setError((e as Error).message || 'Could not save. Please retry.');
      setBusy(false);
    }
  };
  const toggleSubject = (subject: string) => set({
    subjects: draft.subjects.some(s => s.toLowerCase() === subject.toLowerCase())
      ? draft.subjects.filter(s => s.toLowerCase() !== subject.toLowerCase())
      : draft.subjects.length < 6 ? [...draft.subjects, subject] : draft.subjects,
  });
  const addCustom = () => { const s = custom.trim(); if (s) { toggleSubject(s.slice(0, 60)); setCustom(''); } };
  const canContinue = step === 0 ? draft.display_name.trim().length > 0 : step === 2 ? draft.subjects.length > 0 : true;
  const seed = `${workspace}:${draft.avatar_seed}`;

  const body = useMemo(() => {
    switch (step) {
      case 0: return <>
        <View style={styles.hero}><Avatar seed={seed} name={draft.display_name} size={104} /></View>
        <Title text="What should we call you?" sub="It’s how Tayarishe greets you." />
        <Field label="Your name" hideLabel value={draft.display_name} onChangeText={t => set({ display_name: t.slice(0, 40) })}
          placeholder="Your first name" autoFocus={!editing} autoCapitalize="words" returnKeyType="next" accent={draft.accent}
          onSubmitEditing={() => canContinue && go(1)} />
      </>;
      case 1: return <>
        <Title text={`What are you working toward${draft.display_name ? `, ${draft.display_name.trim()}` : ''}?`} sub="Your tutor adapts its questions and feedback to this." />
        {GOALS.map(g => <Choice key={g.value} title={g.title} detail={g.detail} icon={g.icon} selected={draft.goal === g.value}
          accent={draft.accent} onPress={() => set({ goal: g.value })} />)}
      </>;
      case 2: return <>
        <Title text="What are you studying?" sub="Pick up to six. Your answers, quizzes and cards start here." />
        <View style={styles.chips}>
          {[...POPULAR_SUBJECTS, ...draft.subjects.filter(s => !POPULAR_SUBJECTS.some(p => p.toLowerCase() === s.toLowerCase()))].map(s => {
            const on = draft.subjects.some(x => x.toLowerCase() === s.toLowerCase());
            return <PressableScale key={s} onPress={() => toggleSubject(s)} accessibilityLabel={s} accessibilityState={{ selected: on }}
              style={[styles.chip, { backgroundColor: on ? accent.main : colors.surface, borderColor: on ? accent.main : colors.border }]}>
              {on && <Icon name={{ ios: 'checkmark', android: 'check' }} size={13} color="#ffffff" />}
              <Text style={[styles.chipText, { color: on ? '#ffffff' : colors.text }]}>{s}</Text>
            </PressableScale>;
          })}
        </View>
        <View style={styles.addRow}>
          <TextInput accessibilityLabel="Add your own subject" value={custom} onChangeText={setCustom} onSubmitEditing={addCustom}
            placeholder="Add your own…" placeholderTextColor={colors.textFaint} returnKeyType="done"
            style={[styles.addInput, { color: colors.text, backgroundColor: colors.surface, borderColor: colors.border }]} />
          <PressableScale onPress={addCustom} disabled={!custom.trim()} accessibilityLabel="Add subject"
            style={[styles.addButton, { backgroundColor: accent.main }, !custom.trim() && styles.dim]}>
            <Icon name={{ ios: 'plus', android: 'add' }} size={20} color="#ffffff" />
          </PressableScale>
        </View>
        <Text style={[styles.label, { color: colors.textSecondary }]}>Your level</Text>
        <Segmented accent={draft.accent} value={draft.level} onChange={level => set({ level })}
          options={[{ value: 'beginner', label: 'Beginner' }, { value: 'intermediate', label: 'Intermediate' }, { value: 'advanced', label: 'Advanced' }]} />
        {draft.goal === 'exam' && <Field label="Which exam, and when?" accent={draft.accent} value={draft.exam_context}
          onChangeText={t => set({ exam_context: t.slice(0, 200) })} placeholder="KCSE, November 2027" />}
      </>;
      case 3: return <>
        <Title text="How much each day?" sub="Answers, cards and questions all count. You can change this any time." />
        <View style={styles.paces}>
          {/* Each tile sits in a half-width slot: a percentage width on the pressable's inner view would
              resolve against its unsized wrapper and squeeze the text to one letter per line. */}
          {PACES.map(p => <View key={p.value} style={styles.paceSlot}>
            <PressableScale onPress={() => set({ daily_goal: p.value })} accessibilityLabel={`${p.title}, ${p.value} a day`}
              accessibilityState={{ selected: draft.daily_goal === p.value }}
              style={[styles.pace, { backgroundColor: draft.daily_goal === p.value ? accent.soft : colors.surface, borderColor: draft.daily_goal === p.value ? accent.main : colors.border }]}>
              <Text style={[styles.paceValue, { color: draft.daily_goal === p.value ? accent.deep : colors.text }]}>{p.value}</Text>
              <Text style={[styles.paceTitle, { color: colors.text }]}>{p.title}</Text>
              <Text style={[styles.paceDetail, { color: colors.textSecondary }]}>{p.detail}</Text>
            </PressableScale>
          </View>)}
        </View>
      </>;
      default: return <>
        <Title text="Pick your look" sub="Your colour and avatar follow you across the app, on every device." />
        <ShuffleAvatar seed={seed} name={draft.display_name} reduced={reduced} onShuffle={() => set({ avatar_seed: newSeed() })} />
        <View style={styles.swatches}>
          {ACCENTS.map(a => <PressableScale key={a} onPress={() => set({ accent: a })} accessibilityLabel={`${a} colour`} accessibilityState={{ selected: draft.accent === a }}
            style={[styles.swatch, { borderColor: draft.accent === a ? colors[a] : 'transparent' }]}>
            <LinearGradient colors={[colors[a], colors[`${a}Deep`]]} style={styles.swatchFill}>
              {draft.accent === a && <Icon name={{ ios: 'checkmark', android: 'check' }} size={18} color="#ffffff" />}
            </LinearGradient>
          </PressableScale>)}
        </View>
      </>;
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [step, draft, custom, colors, seed, reduced, editing]);

  return <View style={[styles.flex, { backgroundColor: colors.background }]}>
    <LinearGradient pointerEvents="none" colors={[accent.soft, colors.background]} style={[styles.wash, { height: insets.top + 320 }]} />
    <View style={[styles.top, { paddingTop: insets.top + 8 }]}>
      {step > 0 ? <PressableScale onPress={() => go(step - 1)} accessibilityLabel="Back" style={styles.topButton}>
        <Icon name={{ ios: 'chevron.left', android: 'arrow_back' }} size={20} color={colors.text} />
      </PressableScale> : editing ? <PressableScale onPress={() => router.back()} accessibilityLabel="Close" style={styles.topButton}>
        <Icon name={{ ios: 'xmark', android: 'close' }} size={18} color={colors.text} />
      </PressableScale> : <View style={styles.topButton} />}
      <View style={styles.flex}><ProgressBar value={(step + 1) / STEPS} accent={draft.accent} label={`Step ${step + 1} of ${STEPS}`} /></View>
      {!editing ? <PressableScale onPress={() => void finish(true)} accessibilityLabel="Skip for now" style={styles.topButton}>
        <Text style={[styles.skip, { color: colors.textSecondary }]}>Skip</Text>
      </PressableScale> : <View style={styles.topButton} />}
    </View>
    <ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={styles.scroll}>
      <Animated.View key={step} entering={reduced ? undefined : enterFrom(direction)} exiting={reduced ? undefined : LEAVE} style={styles.step}>
        {body}
      </Animated.View>
    </ScrollView>
    <View style={[styles.bottom, { paddingBottom: insets.bottom + 16 }]}>
      <Notice text={error} kind="error" />
      {step < STEPS - 1
        ? <Button label="Continue" accent={draft.accent} icon={{ ios: 'arrow.right', android: 'arrow_forward' }} disabled={!canContinue} onPress={() => go(step + 1)} />
        : <Button label={editing ? 'Save changes' : 'Start learning'} accent={draft.accent} icon={{ ios: 'sparkles', android: 'auto_awesome' }} busy={busy} onPress={() => void finish()} />}
    </View>
  </View>;
}

function Title({ text, sub }: { text: string; sub: string }) {
  const colors = useTheme();
  return <View style={styles.titleBlock}>
    <Text accessibilityRole="header" style={[styles.title, { color: colors.text }]}>{text}</Text>
    <Text style={[styles.sub, { color: colors.textSecondary }]}>{sub}</Text>
  </View>;
}

function Choice({ title, detail, icon, selected, accent, onPress }: { title: string; detail: string; icon: IconName; selected: boolean; accent: Accent; onPress: () => void }) {
  const colors = useTheme();
  const a = accentColors(colors, accent);
  return <PressableScale onPress={onPress} accessibilityLabel={`${title}. ${detail}`} accessibilityState={{ selected }}
    style={[styles.choice, { backgroundColor: selected ? a.soft : colors.surface, borderColor: selected ? a.main : colors.border }]}>
    <View style={[styles.choiceIcon, { backgroundColor: selected ? a.main : colors.backgroundElement }]}><Icon name={icon} size={20} color={selected ? '#ffffff' : colors.textSecondary} /></View>
    <View style={styles.flex}>
      <Text style={[styles.choiceTitle, { color: colors.text }]}>{title}</Text>
      <Text style={[styles.choiceDetail, { color: colors.textSecondary }]}>{detail}</Text>
    </View>
    <View style={[styles.radio, { borderColor: selected ? a.main : colors.border, backgroundColor: selected ? a.main : 'transparent' }]}>
      {selected && <Icon name={{ ios: 'checkmark', android: 'check' }} size={12} color="#ffffff" />}
    </View>
  </PressableScale>;
}

/** The avatar turns over (rotateY, 420ms) as a new one is drawn: the swap happens edge-on, unseen. */
function ShuffleAvatar({ seed, name, reduced, onShuffle }: { seed: string; name: string; reduced: boolean; onShuffle: () => void }) {
  const colors = useTheme();
  const turn = useSharedValue(0);
  const style = useAnimatedStyle(() => ({ transform: [{ perspective: 800 }, { rotateY: `${turn.get()}deg` }] }));
  const shuffle = () => {
    haptics.snap();
    if (reduced) { onShuffle(); return; }
    turn.set(withSequence(withTiming(90, { duration: 210, easing: EASE_IN_OUT }), withTiming(-90, { duration: 0 }), withTiming(0, { duration: 210, easing: EASE_OUT })));
    setTimeout(onShuffle, 210);
  };
  return <View style={styles.shuffle}>
    <Animated.View style={style}><Avatar seed={seed} name={name} size={128} label={`Your avatar${name ? `, ${name}` : ''}`} /></Animated.View>
    <PressableScale onPress={shuffle} accessibilityLabel="Shuffle avatar" style={[styles.shuffleButton, { backgroundColor: colors.surface, borderColor: colors.border }]}>
      <Icon name={{ ios: 'shuffle', android: 'shuffle' }} size={16} color={colors.text} />
      <Text style={[styles.shuffleText, { color: colors.text }]}>Shuffle</Text>
    </PressableScale>
  </View>;
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  wash: { position: 'absolute', top: 0, left: 0, right: 0 },
  top: { flexDirection: 'row', alignItems: 'center', gap: 12, paddingHorizontal: 12 },
  topButton: { width: 52, height: 44, alignItems: 'center', justifyContent: 'center' },
  skip: { fontFamily: Fonts.bodySemi, fontSize: 16 },
  scroll: { paddingHorizontal: 20, paddingTop: 24, paddingBottom: 24 },
  step: { gap: 14 },
  hero: { alignItems: 'center', marginBottom: 6 },
  titleBlock: { gap: 6, marginBottom: 4 },
  title: { fontFamily: Fonts.display, fontSize: 30, letterSpacing: -0.8, lineHeight: 36 },
  sub: { fontFamily: Fonts.body, fontSize: 17, lineHeight: 23 },
  label: { fontFamily: Fonts.bodySemi, fontSize: 15, marginTop: 6 },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  chip: { flexDirection: 'row', alignItems: 'center', gap: 6, minHeight: 40, paddingHorizontal: 14, borderRadius: Radius.pill, borderWidth: 1.5 },
  chipText: { fontFamily: Fonts.bodySemi, fontSize: 15 },
  addRow: { flexDirection: 'row', gap: 8 },
  addInput: { flex: 1, minHeight: 48, borderWidth: 1.5, borderRadius: Radius.md, paddingHorizontal: 14, fontFamily: Fonts.body, fontSize: 16 },
  addButton: { width: 48, height: 48, borderRadius: Radius.md, alignItems: 'center', justifyContent: 'center' },
  dim: { opacity: 0.4 },
  choice: { flexDirection: 'row', alignItems: 'center', gap: 14, padding: 16, borderRadius: Radius.lg, borderWidth: 1.5 },
  choiceIcon: { width: 44, height: 44, borderRadius: 14, alignItems: 'center', justifyContent: 'center' },
  choiceTitle: { fontFamily: Fonts.heading, fontSize: 17 },
  choiceDetail: { fontFamily: Fonts.body, fontSize: 15, lineHeight: 20 },
  radio: { width: 24, height: 24, borderRadius: 12, borderWidth: 2, alignItems: 'center', justifyContent: 'center' },
  paces: { flexDirection: 'row', flexWrap: 'wrap', marginHorizontal: -6 },
  paceSlot: { width: '50%', padding: 6 },
  pace: { padding: 16, borderRadius: Radius.lg, borderWidth: 1.5, gap: 2, minHeight: 124 },
  paceValue: { fontFamily: Fonts.display, fontSize: 30, letterSpacing: -1 },
  paceTitle: { fontFamily: Fonts.heading, fontSize: 16 },
  paceDetail: { fontFamily: Fonts.body, fontSize: 14 },
  shuffle: { alignItems: 'center', gap: 14, marginVertical: 8 },
  shuffleButton: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 16, minHeight: 40, borderRadius: Radius.pill, borderWidth: 1.5 },
  shuffleText: { fontFamily: Fonts.bodyBold, fontSize: 15 },
  swatches: { flexDirection: 'row', justifyContent: 'center', gap: 16, marginTop: 8 },
  swatch: { width: 62, height: 62, borderRadius: 31, borderWidth: 3, padding: 4 },
  swatchFill: { flex: 1, borderRadius: 27, alignItems: 'center', justifyContent: 'center' },
  bottom: { paddingHorizontal: 20, gap: 10 },
});
