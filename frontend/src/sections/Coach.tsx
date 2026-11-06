import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useModelContext } from '../context/ModelContext';
import { Markdown } from '../components/Markdown';
import { Select } from '../components/Select';
import styles from './Coach.module.css';
import { apiFetch } from '../api/access';

interface Result { score: number; feedback: string; key_missed: string[]; hint: string; rubric?: { reasoning: number; accuracy: number; clarity: number } | null }
interface Session {
  id: string; topic: string; mode: string; model: string; index: number; total: number;
  deadline: number; done: boolean; grounding: string;
  sources: { source: string; page: string | number }[];
  question: { type: string; question: string; topic: string; options: Record<string, string>; adaptive?: boolean } | null;
  answers: { question: string; reference: string; explanation: string; result: Result }[];
  summary: { score: number; topics: { topic: string; score: number; missed: string[] }[]; next_actions: string[] } | null;
}
const learnerKey = 'preparationpal.learner';
function learnerId() {
  let id = localStorage.getItem(learnerKey);
  if (!id) { id = crypto.randomUUID(); localStorage.setItem(learnerKey, id); }
  return id;
}
async function request<T>(path: string, body?: unknown): Promise<T> {
  const r = await apiFetch(`/api/coach${path}`, body ? {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  } : undefined);
  const data = await r.json();
  if (!r.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Please check your settings and retry.');
  return data;
}

export function Coach() {
  const { selected } = useModelContext();
  const [learner] = useState(learnerId);
  const [topic, setTopic] = useState('');
  const [mode, setMode] = useState('recap');
  const [difficulty, setDifficulty] = useState('medium');
  const [questionType, setQuestionType] = useState('mixed');
  const [n, setN] = useState(5);
  const [minutes, setMinutes] = useState(0);
  const [session, setSession] = useState<Session | null>(null);
  const [answer, setAnswer] = useState('');
  const [confidence, setConfidence] = useState(3);
  const [feedback, setFeedback] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [clock, setClock] = useState(Date.now());
  const [history, setHistory] = useState<{ sessions: { id: string; topic: string; mode: string; completed: boolean }[]; weak_topics: string[] }>({ sessions: [], weak_topics: [] });
  const refresh = () => request<typeof history>(`/history?learner=${encodeURIComponent(learner)}`).then(setHistory);
  useEffect(() => { refresh().catch(e => setError(e.message)); }, [learner]);
  useEffect(() => {
    const timer = window.setInterval(() => setClock(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);
  const expired = Boolean(session?.deadline && clock >= session.deadline * 1000);
  useEffect(() => {
    if (expired && session && !session.done) {
      request<Session>(`/sessions/${session.id}?learner=${encodeURIComponent(learner)}`)
        .then(setSession).catch(e => setError(e.message));
    }
  }, [expired, session?.id, session?.done, learner]);
  async function run(action: () => Promise<void>) {
    setBusy(true); setError('');
    try { await action(); } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }
  function resume(id: string) { run(async () => {
    setSession(await request<Session>(`/sessions/${id}?learner=${encodeURIComponent(learner)}`));
    setFeedback(false); setAnswer('');
  }); }
  return <div className={styles.scroll}><div className={styles.container}>
    <header className={styles.hero}>
      <h2>What would you like to practise?</h2><p>Choose a topic, answer questions, and review the concepts you missed.</p></header>
    {error && <p role="alert" className={styles.error}>{error}</p>}
    <p className="sr-only" role="status">{busy ? 'Working with your local model. This may take a moment.' : 'Ready'}</p>
    {!session ? <>
      <form className={styles.card} onSubmit={e => { e.preventDefault(); run(async () => {
        setSession(await request<Session>('/sessions', { learner, topic, mode, difficulty, n, minutes, question_type: questionType, model: selected || undefined }));
        setFeedback(false); await refresh();
      }); }}>
        <h3>Study session</h3>
        <div className={styles.modes}>{[
          ['recap', 'Learn & recap', 'Build understanding, then test recall.'],
          ['exam', 'Exam practice', 'Mixed questions, with an optional timer.'],
          ['interview', 'Technical interview', 'Explain your reasoning and tackle follow-ups.'],
          ['review', 'Weak-area review', 'Return to the concepts you missed.'],
        ].map(([id, title, description]) => <button key={id} type="button" disabled={busy} aria-pressed={mode === id}
          className={mode === id ? styles.active : ''} onClick={() => setMode(id)}>
          <strong>{title}</strong><span>{description}</span></button>)}</div>
        <label>Topic, subject, or syllabus focus<input required disabled={busy} maxLength={500} value={topic}
          placeholder="Thermodynamics, molecular biology, quantum mechanics…" onChange={e => setTopic(e.target.value)} /></label>
        <div className={styles.row}>
          {mode !== 'interview' && <Select label="Question format" value={questionType} onChange={setQuestionType}
            disabled={busy} options={Object.entries({ mixed: 'Mixed', mcq: 'Multiple choice', true_false: 'True / false', short_answer: 'Short answer', free_response: 'Extended reasoning' }).map(([value, label]) => ({ value, label }))} />}
          <Select label="Difficulty" value={difficulty} onChange={setDifficulty} disabled={busy}
            options={['easy', 'medium', 'hard', 'mixed'].map(value => ({ value, label: value[0].toUpperCase() + value.slice(1) }))} />
          <Select label="Questions" value={String(n)} onChange={value => setN(Number(value))} disabled={busy}
            options={[3, 5, 10, 15, 20].map(value => ({ value: String(value), label: String(value) }))} />
          {mode === 'exam' && <Select label="Time limit" value={String(minutes)} onChange={value => setMinutes(Number(value))} disabled={busy}
            options={[0, 10, 20, 30, 60].map(value => ({ value: String(value), label: value ? `${value} minutes` : 'Untimed' }))} />}
        </div>
        {mode === 'review' && <p>Priority topics: {history.weak_topics.join(', ') || 'Complete a session to discover weak areas. Your chosen topic will be used for now.'}</p>}
        <p>Uses uploaded material when available. Otherwise, questions are labelled as general model knowledge.</p>
        <button className={styles.primary} disabled={busy || !topic.trim()}>{busy ? 'Preparing your session…' : 'Start preparation'}</button>
      </form>
      {history.sessions.length > 0 && <section className={styles.card}><h3>Your recent sessions</h3>
        {history.sessions.map(s => <button className={styles.history} key={s.id} disabled={busy} onClick={() => resume(s.id)}>
          <span>{s.topic}</span><span>{s.mode} · {s.completed ? 'Results' : 'Resume'} →</span></button>)}</section>}
    </> : <section className={styles.card}>
      <div className={styles.row}><p>{session.mode} · {session.model}</p>
        <button disabled={busy} onClick={() => { setSession(null); setAnswer(''); refresh().catch(e => setError(e.message)); }}>Back to preparation</button></div>
      <p className={styles.grounding}>{session.grounding === 'documents' ? 'Grounded in your documents' : 'General model knowledge · verify important facts'}</p>
      {session.sources.length > 0 && <details><summary>Source material</summary><ul>{session.sources.map((s, i) => <li key={i}>{s.source} · page {s.page}</li>)}</ul></details>}
      {session.deadline > 0 && !session.done && <p role="timer">Time remaining: {Math.max(0, Math.ceil((session.deadline * 1000 - clock) / 1000))} seconds</p>}
      {feedback && session.answers.length > 0 ? <div>
        <h3>Answer feedback · {session.answers[session.answers.length - 1].result.score}/100</h3>
        {session.answers[session.answers.length - 1].result.rubric && <div className={styles.row}>
          <p>Reasoning: {session.answers[session.answers.length - 1].result.rubric!.reasoning}/40</p>
          <p>Accuracy & units: {session.answers[session.answers.length - 1].result.rubric!.accuracy}/40</p>
          <p>Clarity: {session.answers[session.answers.length - 1].result.rubric!.clarity}/20</p>
        </div>}
        <Markdown>{session.answers[session.answers.length - 1].result.feedback}</Markdown>
        <p>{session.answers[session.answers.length - 1].result.hint}</p>
        <details><summary>Reference answer and solution</summary><Markdown>{session.answers[session.answers.length - 1].reference + '\n\n' + session.answers[session.answers.length - 1].explanation}</Markdown></details>
        <button className={styles.primary} onClick={() => { setFeedback(false); setAnswer(''); setConfidence(3); }}> {session.done ? 'View results' : 'Next question'} </button>
      </div> : session.done && session.summary ? <>
        <h3>Session results · {session.summary.score}%</h3>
        <p>{session.answers.length} of {session.total} questions answered. Unanswered questions count as zero.</p>
        {session.summary.topics.map(t => <div key={t.topic} className={styles.history}><strong>{t.topic}: {t.score}%</strong><p>{t.missed.join(', ')}</p></div>)}
        <h3>Your revision plan</h3><ul>{session.summary.next_actions.map(a => <li key={a}>{a}</li>)}</ul>
        <div className={styles.row}><button onClick={() => { setTopic(session.topic); setMode('review'); setSession(null); refresh().catch(e => setError(e.message)); }}>Practise weak areas</button>
          <Link to="/flashcards">Make revision flashcards →</Link><Link to="/agent">Explain with Study Agent →</Link></div>
      </> : session.question && <form onSubmit={e => { e.preventDefault(); run(async () => {
        setSession(await request<Session>(`/sessions/${session.id}/answers`, { learner, index: session.index, answer, confidence }));
        setFeedback(true);
      }); }}>
        <p>Question {session.index + 1} / {session.total} · {session.question.topic}</p>
        {session.question.adaptive && <p>A targeted question to reinforce the concept you just missed.</p>}
        <Markdown>{session.question.question}</Markdown>
        {['mcq', 'true_false'].includes(session.question.type) ? <fieldset><legend>Your answer</legend>
          {Object.entries(session.question.type === 'true_false' ? { True: 'True', False: 'False' } : session.question.options).map(([key, value]) =>
            <label className={styles.choice} key={key}><input type="radio" name="answer" value={key} required checked={answer === key} onChange={() => setAnswer(key)} />{key}: {value}</label>)}
        </fieldset> : <label>Your reasoning<textarea required rows={7} maxLength={20000} value={answer} onChange={e => setAnswer(e.target.value)} placeholder="Show assumptions, steps, units, and conclusions." /></label>}
        <Select label="Confidence" value={String(confidence)} onChange={value => setConfidence(Number(value))} disabled={busy}
          options={[1, 2, 3, 4, 5].map(value => ({ value: String(value), label: `${value} / 5${value === 1 ? ' — guessing' : value === 5 ? ' — confident' : ''}` }))} />
        <button className={styles.primary} disabled={busy || !answer.trim() || expired}>{busy ? 'Evaluating your answer…' : 'Submit answer'}</button>
      </form>}
    </section>}
  </div></div>;
}
