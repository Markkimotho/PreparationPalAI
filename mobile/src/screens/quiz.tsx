import { useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import Animated, { FadeInDown } from 'react-native-reanimated';

import { Celebration } from '@/components/celebration';
import { Body, Button, Card, Field, Icon, Notice, OptionButton, ProgressBar, Screen, Segmented, type OptionState } from '@/components/ui';
import { EASE_OUT } from '@/constants/motion';
import { Fonts } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import { postJson } from '@/utils/api';
import { haptics } from '@/utils/haptics';
import { recordStudy } from '@/utils/streak';

interface Question { question: string; options?: Record<string, string>; correct?: string; explanation?: string; source?: string }

// Questions arrive together, in reading order: a short non-uniform stagger (50, 90, 120, …ms), capped.
const enterQuestion = (i: number) => FadeInDown.duration(260).delay(Math.min(240, [0, 50, 90, 120][i] ?? 120 + i * 20)).easing(EASE_OUT)
  .withInitialValues({ opacity: 0, transform: [{ translateY: 10 }] });

export function Quiz() {
  const colors = useTheme();
  const [topic, setTopic] = useState('');
  const [count, setCount] = useState<'5' | '10'>('5');
  const [questions, setQuestions] = useState<Question[]>([]);
  const [answers, setAnswers] = useState<Record<number, string>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const generate = async () => {
    setBusy(true); setError(''); setQuestions([]); setAnswers({});
    try {
      setQuestions(await postJson<Question[]>('/api/quiz/generate', { topic: topic.trim(), n: Number(count), question_type: 'mcq' }));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const choose = (i: number, letter: string) => {
    if (letter === questions[i].correct) haptics.success(); else haptics.error();
    setAnswers(a => ({ ...a, [i]: letter }));
    recordStudy().catch(() => undefined);
  };

  const answered = Object.keys(answers).length;
  const score = questions.reduce((n, q, i) => n + (answers[i] && answers[i] === q.correct ? 1 : 0), 0);
  const finished = questions.length > 0 && answered === questions.length;
  const ratio = questions.length ? score / questions.length : 0;
  const stateOf = (q: Question, i: number, letter: string): OptionState => {
    const chosen = answers[i];
    if (!chosen) return 'idle';
    if (letter === q.correct) return 'correct';
    return letter === chosen ? 'wrong' : 'dim';
  };

  return <Screen title="Quiz" subtitle="Test yourself in a few minutes." accent="amber">
    <Card>
      <Field label="Topic" accent="amber" value={topic} onChangeText={setTopic} placeholder="Photosynthesis, SQL joins, …" />
      <Segmented accent="amber" options={[{ value: '5', label: '5 questions' }, { value: '10', label: '10 questions' }]} value={count} onChange={setCount} />
      <Button label={busy ? 'Writing your quiz…' : 'Make a quiz'} accent="amber" icon={{ ios: 'wand.and.stars', android: 'auto_fix_high' }}
        busy={busy} disabled={!topic.trim()} onPress={() => void generate()} />
    </Card>
    <Notice text={error} kind="error" />

    {questions.length > 0 && <View style={styles.progress}>
      <Text style={[styles.progressText, { color: colors.textSecondary }]}>{`${answered} of ${questions.length} answered`}</Text>
      <ProgressBar value={answered / questions.length} accent="amber" label="Quiz progress" />
    </View>}

    {questions.map((q, i) => <Animated.View key={`${q.question}-${i}`} entering={enterQuestion(i)}>
      <Card>
        <View style={styles.qHead}>
          <View style={[styles.number, { backgroundColor: colors.amberSoft }]}><Text style={[styles.numberText, { color: colors.amberDeep }]}>{i + 1}</Text></View>
          <Text accessibilityRole="header" style={[styles.question, { color: colors.text }]}>{q.question}</Text>
        </View>
        {Object.entries(q.options ?? {}).map(([letter, text]) => <OptionButton key={letter} letter={letter} text={text} accent="amber"
          state={stateOf(q, i, letter)} disabled={!!answers[i]} onPress={() => choose(i, letter)} />)}
        {answers[i] && <View style={[styles.feedback, { backgroundColor: answers[i] === q.correct ? colors.successSoft : colors.dangerSoft }]}>
          <Body>{answers[i] === q.correct ? 'Correct.' : `Not quite: the answer is ${q.correct}.`} {q.explanation ?? ''}</Body>
        </View>}
      </Card>
    </Animated.View>)}

    {finished && <Card tone="soft" accent={ratio >= 0.6 ? 'green' : 'amber'} style={styles.result}>
      <Celebration play={ratio >= 0.6} />
      <View style={[styles.trophy, { backgroundColor: ratio >= 0.6 ? colors.green : colors.amber }]}>
        <Icon name={ratio >= 0.6 ? { ios: 'trophy.fill', android: 'emoji_events' } : { ios: 'arrow.triangle.2.circlepath', android: 'replay' }} size={28} color="#ffffff" />
      </View>
      <Text style={[styles.scoreBig, { color: colors.text }]}>{`${Math.round(ratio * 100)}%`}</Text>
      <Notice text={`You scored ${score} of ${questions.length}.`} />
      <Body muted center>{ratio === 1 ? 'Perfect. You know this cold.' : ratio >= 0.6 ? 'Nice work. Review the ones you missed and go again.' : 'Every miss is a lesson. Try another round.'}</Body>
      <Button label="New quiz" variant="secondary" accent="amber" onPress={() => { setQuestions([]); setAnswers({}); }} />
    </Card>}
  </Screen>;
}

const styles = StyleSheet.create({
  progress: { gap: 8 },
  progressText: { fontFamily: Fonts.bodySemi, fontSize: 14 },
  qHead: { flexDirection: 'row', gap: 12, alignItems: 'flex-start', marginBottom: 4 },
  number: { width: 30, height: 30, borderRadius: 10, alignItems: 'center', justifyContent: 'center' },
  numberText: { fontFamily: Fonts.display, fontSize: 15 },
  question: { flex: 1, fontFamily: Fonts.heading, fontSize: 18, lineHeight: 24 },
  feedback: { borderRadius: 12, padding: 12 },
  result: { alignItems: 'center', gap: 12, paddingVertical: 24, overflow: 'visible' },
  trophy: { width: 60, height: 60, borderRadius: 20, alignItems: 'center', justifyContent: 'center' },
  scoreBig: { fontFamily: Fonts.display, fontSize: 44, letterSpacing: -1.5 },
});
