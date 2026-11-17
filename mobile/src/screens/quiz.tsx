import { useState } from 'react';

import { Body, Button, Card, Field, Heading, Notice, Screen, Segmented } from '@/components/ui';
import { postJson } from '@/utils/api';

interface Question { question: string; options?: Record<string, string>; correct?: string; explanation?: string; source?: string }

export function Quiz() {
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

  const answered = Object.keys(answers).length;
  const score = questions.reduce((n, q, i) => n + (answers[i] && answers[i] === q.correct ? 1 : 0), 0);

  return <Screen>
    <Heading>Quiz</Heading>
    <Field label="Topic" value={topic} onChangeText={setTopic} placeholder="Photosynthesis, SQL joins, …" />
    <Segmented options={[{ value: '5', label: '5 questions' }, { value: '10', label: '10 questions' }]} value={count} onChange={setCount} />
    <Button label={busy ? 'Writing your quiz…' : 'Make a quiz'} busy={busy} disabled={!topic.trim()} onPress={() => void generate()} />
    <Notice text={error} kind="error" />
    {questions.map((q, i) => <Card key={i}>
      <Heading level={2}>{`${i + 1}. ${q.question}`}</Heading>
      {Object.entries(q.options ?? {}).map(([letter, text]) => {
        const chosen = answers[i];
        const mark = chosen ? (letter === q.correct ? ' ✓' : letter === chosen ? ' ✗' : '') : '';
        return <Button key={letter} variant="secondary" label={`${letter}. ${text}${mark}`} disabled={!!chosen}
          onPress={() => setAnswers(a => ({ ...a, [i]: letter }))} />;
      })}
      {answers[i] && <Body>{answers[i] === q.correct ? 'Correct.' : `Not quite: the answer is ${q.correct}.`} {q.explanation ?? ''}</Body>}
    </Card>)}
    {questions.length > 0 && answered === questions.length && <Notice text={`You scored ${score} of ${questions.length}.`} />}
  </Screen>;
}
