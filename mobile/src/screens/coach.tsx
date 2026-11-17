import { useState } from 'react';

import { Body, Button, Card, Field, Heading, Notice, Screen, Segmented } from '@/components/ui';
import { postJson } from '@/utils/api';

type Mode = 'recap' | 'exam' | 'interview';
interface Question { type: string; question: string; options?: Record<string, string> }
interface Answer { result: { score: number; feedback: string; hint?: string } }
interface Session {
  id: string; index: number; total: number; done: boolean; question: Question | null; answers: Answer[];
  summary: { score: number; next_actions: string[] } | null;
}

const LEARNER = 'me';   // each signed-in account is its own private workspace

export function Coach() {
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
  const submit = (text: string) => run(() => postJson<Session>(`/api/coach/sessions/${session!.id}/answers`,
    { learner: LEARNER, answer: text, index: session!.index, confidence: 3 }));

  const last = session?.answers[session.answers.length - 1]?.result;

  return <Screen>
    <Heading>Coach</Heading>
    {!session && <>
      <Field label="What are you preparing for?" value={topic} onChangeText={setTopic} placeholder="Data structures interview" />
      <Segmented options={[{ value: 'recap', label: 'Recap' }, { value: 'exam', label: 'Exam' }, { value: 'interview', label: 'Interview' }]}
        value={mode} onChange={setMode} />
      <Button label={busy ? 'Preparing questions…' : 'Start practice'} busy={busy} disabled={!topic.trim()} onPress={() => void start()} />
    </>}
    <Notice text={error} kind="error" />
    {last && <Card><Heading level={2}>{`Score ${last.score}/100`}</Heading><Body>{last.feedback}</Body>{last.hint && <Body muted>{last.hint}</Body>}</Card>}
    {session && !session.done && session.question && <Card>
      <Body muted>{`Question ${session.index + 1} of ${session.total}`}</Body>
      <Heading level={2}>{session.question.question}</Heading>
      {session.question.options ? Object.entries(session.question.options).map(([letter, text]) =>
        <Button key={letter} variant="secondary" label={`${letter}. ${text}`} disabled={busy} onPress={() => void submit(letter)} />) : <>
        <Field label="Your answer" value={answer} onChangeText={setAnswer} multiline />
        <Button label="Submit answer" busy={busy} disabled={!answer.trim()} onPress={() => void submit(answer.trim())} />
      </>}
    </Card>}
    {session?.done && session.summary && <Card>
      <Heading level={2}>{`Overall ${session.summary.score}/100`}</Heading>
      {session.summary.next_actions.map((a, i) => <Body key={i}>{`• ${a}`}</Body>)}
      <Button label="Practise again" variant="secondary" onPress={() => setSession(null)} />
    </Card>}
  </Screen>;
}
