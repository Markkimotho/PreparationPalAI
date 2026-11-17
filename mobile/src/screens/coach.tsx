import { useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import Animated, { FadeInDown } from 'react-native-reanimated';

import { Celebration } from '@/components/celebration';
import { Body, Button, Card, Field, Icon, Notice, OptionButton, ProgressBar, Screen, Segmented, type IconName } from '@/components/ui';
import { EASE_OUT } from '@/constants/motion';
import { Fonts } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import { postJson } from '@/utils/api';
import { haptics } from '@/utils/haptics';
import { recordStudy } from '@/utils/streak';

type Mode = 'recap' | 'exam' | 'interview';
interface Question { type: string; question: string; options?: Record<string, string> }
interface Answer { result: { score: number; feedback: string; hint?: string } }
interface Session {
  id: string; index: number; total: number; done: boolean; question: Question | null; answers: Answer[];
  summary: { score: number; next_actions: string[] } | null;
}

const LEARNER = 'me';   // each signed-in account is its own private workspace
const MODES: { value: Mode; label: string; icon: IconName; about: string }[] = [
  { value: 'recap', label: 'Recap', icon: { ios: 'arrow.counterclockwise', android: 'history' }, about: 'Quick questions to lock in what you studied.' },
  { value: 'exam', label: 'Exam', icon: { ios: 'doc.text.fill', android: 'description' }, about: 'Exam-style questions, scored the way a marker would.' },
  { value: 'interview', label: 'Interview', icon: { ios: 'person.2.fill', android: 'groups' }, about: 'Answer out loud in your head, then type it. Get interviewer feedback.' },
];
const ENTER = FadeInDown.duration(220).easing(EASE_OUT).withInitialValues({ opacity: 0, transform: [{ translateY: 8 }] });

export function Coach() {
  const colors = useTheme();
  const [topic, setTopic] = useState('');
  const [mode, setMode] = useState<Mode>('recap');
  const [session, setSession] = useState<Session | null>(null);
  const [answer, setAnswer] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const run = async (work: () => Promise<Session>) => {
    setBusy(true); setError('');
    try { setSession(await work()); setAnswer(''); } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  };
  const start = () => run(() => postJson<Session>('/api/coach/sessions', { learner: LEARNER, topic: topic.trim(), mode, n: 5 }));
  const submit = (text: string) => run(async () => {
    const next = await postJson<Session>(`/api/coach/sessions/${session!.id}/answers`, { learner: LEARNER, answer: text, index: session!.index, confidence: 3 });
    const graded = next.answers[next.answers.length - 1]?.result;
    if (graded && graded.score >= 70 && !next.done) haptics.success();
    recordStudy().catch(() => undefined);
    return next;
  });

  const last = session?.answers[session.answers.length - 1]?.result;
  const about = MODES.find(m => m.value === mode)!;
  const good = (session?.summary?.score ?? 0) >= 70;

  return <Screen title="Coach" subtitle="Practise for the real thing." accent="coral">
    {!session && <Card>
      <Field label="What are you preparing for?" accent="coral" value={topic} onChangeText={setTopic} placeholder="Data structures interview" />
      <Segmented accent="coral" options={MODES.map(m => ({ value: m.value, label: m.label, icon: m.icon }))} value={mode} onChange={setMode} />
      <View style={[styles.about, { backgroundColor: colors.coralSoft }]}>
        <Icon name={about.icon} size={18} color={colors.coralDeep} />
        <Text style={[styles.aboutText, { color: colors.text }]}>{about.about}</Text>
      </View>
      <Button label={busy ? 'Preparing questions…' : 'Start practice'} accent="coral" icon={{ ios: 'play.fill', android: 'play_arrow' }}
        busy={busy} disabled={!topic.trim()} onPress={() => void start()} />
    </Card>}
    <Notice text={error} kind="error" />

    {session && !session.done && <View style={styles.progress}>
      <Text style={[styles.progressText, { color: colors.textSecondary }]}>{`Question ${session.index + 1} of ${session.total}`}</Text>
      <ProgressBar value={session.index / session.total} accent="coral" label="Practice progress" />
    </View>}

    {last && <Animated.View key={`fb-${session?.answers.length}`} entering={ENTER}>
      <Card tone="soft" accent={last.score >= 70 ? 'green' : 'amber'}>
        <View style={styles.scoreRow}>
          <ScoreBadge score={last.score} />
          <Text accessibilityRole="header" style={[styles.scoreTitle, { color: colors.text }]}>{`Score ${last.score}/100`}</Text>
        </View>
        <Body>{last.feedback}</Body>
        {last.hint && <Body muted>{last.hint}</Body>}
      </Card>
    </Animated.View>}

    {session && !session.done && session.question && <Animated.View key={`q-${session.index}`} entering={ENTER}>
      <Card>
        <Text accessibilityRole="header" style={[styles.question, { color: colors.text }]}>{session.question.question}</Text>
        {session.question.options ? Object.entries(session.question.options).map(([letter, text]) =>
          <OptionButton key={letter} letter={letter} text={text} accent="coral" disabled={busy} onPress={() => void submit(letter)} />) : <>
          <Field label="Your answer" accent="coral" value={answer} onChangeText={setAnswer} multiline style={styles.answer} />
          <Button label="Submit answer" accent="coral" icon={{ ios: 'paperplane.fill', android: 'send' }} busy={busy} disabled={!answer.trim()} onPress={() => void submit(answer.trim())} />
        </>}
      </Card>
    </Animated.View>}

    {session?.done && session.summary && <Card tone="soft" accent={good ? 'green' : 'coral'} style={styles.summary}>
      <Celebration play={good} />
      <ScoreBadge score={session.summary.score} large />
      <Text accessibilityRole="header" style={[styles.overall, { color: colors.text }]}>{`Overall ${session.summary.score}/100`}</Text>
      <View style={styles.actions}>
        <Text style={[styles.actionsTitle, { color: colors.textSecondary }]}>What to do next</Text>
        {session.summary.next_actions.map((a, i) => <Body key={i}>{`• ${a}`}</Body>)}
      </View>
      <Button label="Practise again" variant="secondary" accent="coral" icon={{ ios: 'arrow.clockwise', android: 'refresh' }} onPress={() => setSession(null)} />
    </Card>}
  </Screen>;
}

function ScoreBadge({ score, large }: { score: number; large?: boolean }) {
  const colors = useTheme();
  const color = score >= 70 ? colors.green : score >= 40 ? colors.amber : colors.coral;
  const size = large ? 76 : 44;
  return <View accessibilityElementsHidden importantForAccessibility="no-hide-descendants"
    style={[styles.badge, { width: size, height: size, borderRadius: size / 2, borderColor: color }]}>
    <Text style={[styles.badgeText, { color, fontSize: large ? 26 : 16 }]}>{score}</Text>
  </View>;
}

const styles = StyleSheet.create({
  about: { flexDirection: 'row', gap: 10, alignItems: 'center', padding: 12, borderRadius: 12 },
  aboutText: { flex: 1, fontFamily: Fonts.body, fontSize: 15, lineHeight: 21 },
  progress: { gap: 8 },
  progressText: { fontFamily: Fonts.bodySemi, fontSize: 14 },
  scoreRow: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  scoreTitle: { fontFamily: Fonts.heading, fontSize: 18 },
  question: { fontFamily: Fonts.heading, fontSize: 20, lineHeight: 27, letterSpacing: -0.2, marginBottom: 4 },
  answer: { minHeight: 120, textAlignVertical: 'top' },
  summary: { alignItems: 'center', gap: 12, paddingVertical: 24, overflow: 'visible' },
  overall: { fontFamily: Fonts.display, fontSize: 26, letterSpacing: -0.6 },
  actions: { alignSelf: 'stretch', gap: 6 },
  actionsTitle: { fontFamily: Fonts.bodyBold, fontSize: 13, letterSpacing: 0.4, textTransform: 'uppercase' },
  badge: { borderWidth: 4, alignItems: 'center', justifyContent: 'center' },
  badgeText: { fontFamily: Fonts.display },
});
