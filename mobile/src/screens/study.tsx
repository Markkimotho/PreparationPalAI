import { useCallback, useEffect, useMemo, useRef, useState, type ComponentRef } from 'react';
import { ScrollView, StyleSheet, Text, View } from 'react-native';
import Animated, { FadeInDown, useAnimatedStyle, useReducedMotion, useSharedValue, withDelay, withRepeat, withSequence, withTiming } from 'react-native-reanimated';

import { Avatar } from '@/components/avatar';
import { MasteryDial } from '@/components/illustrations';
import Markdown from '@/components/markdown';
import { Body, Button, Card, Field, Icon, Notice, Pill, PressableScale, Screen, Segmented, type IconName } from '@/components/ui';
import { EASE_IN_OUT, EASE_OUT } from '@/constants/motion';
import { Fonts, Radius } from '@/constants/theme';
import { useColorScheme } from '@/hooks/use-color-scheme';
import { useProfile } from '@/hooks/use-profile';
import { useTheme } from '@/hooks/use-theme';
import { stream } from '@/utils/api';
import { haptics } from '@/utils/haptics';
import { currentStreak, recordStudy, todayCount } from '@/utils/streak';
import { studyIdeas } from '@/utils/suggestions';
import { pickAndUpload } from '@/utils/upload';

type Mode = 'notes' | 'tutor' | 'code';
interface Message { role: 'you' | 'pal'; text: string; sources?: string[] }

const MODES: Record<Mode, { label: string; icon: IconName; path: string; body: (text: string, thread: string) => object; hint: string }> = {
  notes: { label: 'My notes', icon: { ios: 'doc.text.fill', android: 'description' }, path: '/api/chat/stream',
    body: (q, t) => ({ question: q, session_id: t }), hint: 'Ask about the notes you added.' },
  tutor: { label: 'Tutor', icon: { ios: 'graduationcap.fill', android: 'school' }, path: '/api/agent/stream',
    body: (m, t) => ({ message: m, thread_id: t }), hint: 'A tutor that can quiz you and explain.' },
  code: { label: 'Code', icon: { ios: 'chevron.left.forwardslash.chevron.right', android: 'code' }, path: '/api/code-chat/stream',
    body: (m, t) => ({ message: m, thread_id: t }), hint: 'Debugging, design and trade-offs.' },
};
const newThread = () => Math.random().toString(36).slice(2, 12);
const greeting = (hour: number) => hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening';
const ENTER_BUBBLE = FadeInDown.duration(150).easing(EASE_OUT).withInitialValues({ opacity: 0, transform: [{ translateY: 6 }] });

export function Study() {
  const colors = useTheme();
  const dark = useColorScheme() === 'dark';
  const { profile, workspace } = useProfile();
  const accent = profile.accent;
  const name = profile.display_name.trim();
  const [mode, setMode] = useState<Mode>('notes');
  const [threads] = useState<Record<Mode, string>>({ notes: newThread(), tutor: newThread(), code: newThread() });
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [streak, setStreak] = useState(0);
  const [today, setToday] = useState(0);
  const abort = useRef<AbortController | null>(null);
  const scroll = useRef<ComponentRef<typeof ScrollView>>(null);

  const refreshProgress = useCallback(() => {
    currentStreak().then(s => setStreak(s.days)).catch(() => undefined);
    todayCount().then(setToday).catch(() => undefined);
  }, []);
  useEffect(() => { refreshProgress(); }, [refreshProgress]);
  const hello = useMemo(() => greeting(new Date().getHours()), []);

  const send = async (override?: string) => {
    const text = (override ?? input).trim();
    if (!text || busy) return;
    setInput(''); setError(''); setBusy(true);
    setMessages(m => [...m, { role: 'you', text }, { role: 'pal', text: '' }]);
    recordStudy().then(refreshProgress).catch(() => undefined);
    const appendToLast = (change: (m: Message) => Message) => setMessages(all => [...all.slice(0, -1), change(all[all.length - 1])]);
    abort.current = new AbortController();
    try {
      await stream(MODES[mode].path, MODES[mode].body(text, threads[mode]), event => {
        if (event.type === 'token') appendToLast(m => ({ ...m, text: m.text + event.text }));
        if (event.type === 'sources') appendToLast(m => ({ ...m, sources: event.sources.map(s => s.source) }));
        if (event.type === 'error') setError(event.message);
      }, abort.current.signal);
    } catch (e) {
      if ((e as Error).name !== 'AbortError') setError((e as Error).message);
    } finally {
      setBusy(false);
      abort.current = null;
    }
  };

  const upload = async () => {
    setError(''); setNotice('');
    try {
      const queued = await pickAndUpload();
      if (queued) { haptics.success(); setNotice('Your file is being read. It will be searchable in a minute.'); }
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const followAnswer = useCallback(() => { if (messages.length) scroll.current?.scrollToEnd({ animated: true }); }, [messages.length]);
  const current = MODES[mode];
  const ideas = studyIdeas(mode, profile);
  const goalDone = today >= profile.daily_goal;

  return <Screen title="Study" accent={accent} scrollRef={scroll} onContentSizeChange={followAnswer}
    eyebrow={<Text style={[styles.eyebrow, { color: colors.textSecondary }]}>{name ? `${hello}, ${name}` : hello}</Text>}
    right={<Avatar seed={`${workspace}:${profile.avatar_seed}`} name={name} size={46} label={name ? `${name}'s avatar` : 'Your avatar'} />}>
    {messages.length === 0 && <Card style={styles.today}>
      <MasteryDial value={Math.min(1, today / Math.max(1, profile.daily_goal))} size={84} color={colors[accent]} track={colors.backgroundSelected}>
        <Text style={[styles.todayCount, { color: colors.text }]}>{today}</Text>
      </MasteryDial>
      <View style={styles.flex}>
        <Text style={[styles.todayTitle, { color: colors.text }]}>{goalDone ? 'Daily goal reached' : `${Math.max(0, profile.daily_goal - today)} to go today`}</Text>
        <Text style={[styles.todayDetail, { color: colors.textSecondary }]}>{`${today} of ${profile.daily_goal} today`}</Text>
        <Pill accent={streak > 0 ? 'amber' : accent} icon={{ ios: 'flame.fill', android: 'local_fire_department' }}
          label={streak > 0 ? `${streak}-day streak` : 'Start a streak today'} />
      </View>
    </Card>}
    <Segmented accent={accent} options={(Object.keys(MODES) as Mode[]).map(m => ({ value: m, label: MODES[m].label, icon: MODES[m].icon }))} value={mode}
      onChange={m => { setMode(m); setMessages([]); setError(''); }} />

    {messages.length === 0 ? <Card tone="soft" accent={accent} style={styles.empty}>
      <View style={[styles.emptyIcon, { backgroundColor: colors[accent] }]}><Icon name={current.icon} size={26} color="#ffffff" /></View>
      <Text style={[styles.emptyTitle, { color: colors.text }]}>{current.hint}</Text>
      <View style={styles.ideas}>
        {ideas.map(idea => <PressableScale key={idea} onPress={() => setInput(idea)} accessibilityLabel={`Use suggestion: ${idea}`}
          style={[styles.idea, { backgroundColor: colors.surface, borderColor: colors.border }]}>
          <Icon name={{ ios: 'sparkle', android: 'auto_awesome' }} size={14} color={colors[accent]} />
          <Text style={[styles.ideaText, { color: colors.text }]}>{idea}</Text>
        </PressableScale>)}
      </View>
      {mode === 'notes' && <Button label="Add notes (PDF or photo)" variant="secondary" icon={{ ios: 'plus.circle.fill', android: 'add_circle' }} onPress={() => void upload()} />}
    </Card> : messages.map((m, i) => <Animated.View key={i} entering={ENTER_BUBBLE}>
      {m.role === 'you'
        ? <View style={[styles.mine, { backgroundColor: colors[accent] }]}><Text style={styles.mineText}>{m.text}</Text></View>
        : <View style={styles.palRow}>
          <View style={[styles.avatar, { backgroundColor: colors.brand }]}><View style={[styles.avatarInner, { backgroundColor: colors.mint }]} /></View>
          <View style={[styles.theirs, { backgroundColor: colors.surface, borderColor: colors.border }]}>
            {m.text ? <Markdown text={m.text} dark={dark} dom={{ matchContents: true, scrollEnabled: false }} />
              : busy && i === messages.length - 1 ? <Typing color={colors[accent]} /> : <Body muted>…</Body>}
            {!!m.sources?.length && <View style={styles.sources}>
              <Icon name={{ ios: 'doc.text', android: 'description' }} size={13} color={colors.textSecondary} />
              <Text style={[styles.sourcesText, { color: colors.textSecondary }]}>Sources: {m.sources.join(', ')}</Text>
            </View>}
          </View>
        </View>}
    </Animated.View>)}

    <Notice text={notice} />
    <Notice text={error} kind="error" />
    {messages.length > 0 && mode === 'notes' && <Button label="Add notes (PDF or photo)" variant="ghost" compact icon={{ ios: 'plus.circle', android: 'add_circle' }} onPress={() => void upload()} />}

    <View style={[styles.composer, { backgroundColor: colors.surface, borderColor: colors.border, shadowColor: colors.shadow }]}>
      <View style={styles.flex}>
        <Field label="Your question" hideLabel value={input} onChangeText={setInput} multiline editable={!busy}
          placeholder="Ask anything…" style={styles.composerInput} />
      </View>
      {busy
        ? <SendButton label="Stop" icon={{ ios: 'stop.fill', android: 'stop' }} color={colors.coral} onPress={() => abort.current?.abort()} />
        : <SendButton label="Send" icon={{ ios: 'arrow.up', android: 'arrow_upward' }} color={colors[accent]} disabled={!input.trim()} onPress={() => void send()} />}
    </View>
  </Screen>;
}

function SendButton({ label, icon, color, onPress, disabled }: { label: string; icon: IconName; color: string; onPress: () => void; disabled?: boolean }) {
  return <PressableScale onPress={onPress} disabled={disabled} accessibilityLabel={label} style={[styles.send, { backgroundColor: color }, disabled && styles.dim]}>
    <Icon name={icon} size={20} color="#ffffff" />
  </PressableScale>;
}

/** Three dots that bounce while the first words are on their way (screen readers hear "Thinking…"). */
function Typing({ color }: { color: string }) {
  return <View accessible accessibilityLabel="Thinking…" style={styles.typing}>{[0, 1, 2].map(i => <Dot key={i} index={i} color={color} />)}</View>;
}

function Dot({ index, color }: { index: number; color: string }) {
  const reduced = useReducedMotion();
  const y = useSharedValue(0);
  useEffect(() => {
    if (reduced) return;
    y.set(withDelay(index * 120, withRepeat(withSequence(withTiming(-5, { duration: 260, easing: EASE_OUT }), withTiming(0, { duration: 260, easing: EASE_IN_OUT }), withTiming(0, { duration: 300 })), -1)));
  }, [index, reduced, y]);
  const style = useAnimatedStyle(() => ({ transform: [{ translateY: y.get() }], opacity: 0.45 + Math.abs(y.get()) / 10 }));
  return <Animated.View style={[styles.dot, { backgroundColor: color }, style]} />;
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  eyebrow: { fontFamily: Fonts.bodySemi, fontSize: 15 },
  today: { flexDirection: 'row', alignItems: 'center', gap: 16 },
  todayCount: { fontFamily: Fonts.display, fontSize: 24, letterSpacing: -0.6 },
  todayTitle: { fontFamily: Fonts.heading, fontSize: 18 },
  todayDetail: { fontFamily: Fonts.body, fontSize: 15, marginBottom: 6 },
  empty: { alignItems: 'center', gap: 14, paddingVertical: 24 },
  emptyIcon: { width: 56, height: 56, borderRadius: 18, alignItems: 'center', justifyContent: 'center', transform: [{ rotateZ: '-6deg' }] },
  emptyTitle: { fontFamily: Fonts.heading, fontSize: 18, textAlign: 'center' },
  ideas: { alignSelf: 'stretch', gap: 8 },
  idea: { flexDirection: 'row', alignItems: 'center', gap: 8, minHeight: 44, paddingHorizontal: 14, borderRadius: Radius.md, borderWidth: StyleSheet.hairlineWidth },
  ideaText: { flex: 1, fontFamily: Fonts.bodySemi, fontSize: 15 },
  mine: { alignSelf: 'flex-end', maxWidth: '85%', paddingHorizontal: 16, paddingVertical: 11, borderRadius: 20, borderBottomRightRadius: 6 },
  mineText: { color: '#ffffff', fontFamily: Fonts.body, fontSize: 17, lineHeight: 23 },
  palRow: { flexDirection: 'row', gap: 10, alignItems: 'flex-start' },
  avatar: { width: 30, height: 30, borderRadius: 9, alignItems: 'center', justifyContent: 'center', transform: [{ rotateZ: '45deg' }], marginTop: 4 },
  avatarInner: { width: 13, height: 13, borderRadius: 3 },
  theirs: { flex: 1, paddingHorizontal: 14, paddingVertical: 12, borderRadius: 20, borderTopLeftRadius: 6, borderWidth: StyleSheet.hairlineWidth, gap: 8 },
  sources: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  sourcesText: { fontFamily: Fonts.bodySemi, fontSize: 13 },
  composer: { flexDirection: 'row', alignItems: 'flex-end', gap: 8, padding: 6, borderRadius: 24, borderWidth: StyleSheet.hairlineWidth,
    shadowOpacity: 0.08, shadowRadius: 14, shadowOffset: { width: 0, height: 6 }, elevation: 2 },
  composerInput: { borderWidth: 0, minHeight: 44, maxHeight: 140, backgroundColor: 'transparent', paddingVertical: 10 },
  send: { width: 44, height: 44, borderRadius: 22, alignItems: 'center', justifyContent: 'center' },
  dim: { opacity: 0.4 },
  typing: { flexDirection: 'row', gap: 5, paddingVertical: 8 },
  dot: { width: 8, height: 8, borderRadius: 4 },
});
