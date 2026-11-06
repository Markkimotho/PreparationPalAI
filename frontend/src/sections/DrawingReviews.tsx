import { useEffect, useState } from 'react';
import { apiFetch } from '../api/access';
import { useModelContext } from '../context/ModelContext';
import { Markdown } from '../components/Markdown';
import { Select } from '../components/Select';
import styles from './DrawingReviews.module.css';

interface Review { kind: string; feedback: string; observations?: string[]; improvements?: string[]; score: number | null; model?: string }
interface Drawing { id: string; question: string; explanation: string; status: string; created: number; reviews: Review[] }
async function request<T>(path: string, body?: unknown): Promise<T> {
  const response = await apiFetch(`/api/drawings${path}`, body ? { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) } : undefined);
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'The drawing request failed.');
  return data;
}
function DrawingImage({ id }: { id: string }) {
  const [url, setUrl] = useState('');
  const [error, setError] = useState('');
  useEffect(() => {
    let active = true; let imageUrl = '';
    apiFetch(`/api/drawings/${id}/image`).then(async response => {
      if (!response.ok) throw new Error('Could not load this drawing.');
      imageUrl = URL.createObjectURL(await response.blob());
      if (active) setUrl(imageUrl); else URL.revokeObjectURL(imageUrl);
    }).catch(e => { if (active) setError(e.message); });
    return () => { active = false; if (imageUrl) URL.revokeObjectURL(imageUrl); };
  }, [id]);
  return error ? <p role="alert">{error}</p> : url ? <img className={styles.image} src={url} alt="Submitted learner drawing" /> : <p role="status">Loading drawing…</p>;
}

export function DrawingReviews() {
  const { selected } = useModelContext();
  const [drawings, setDrawings] = useState<Drawing[]>([]);
  const [canReview, setCanReview] = useState(false);
  const [active, setActive] = useState('');
  const [models, setModels] = useState<string[]>([]);
  const [vision, setVision] = useState('');
  const [feedback, setFeedback] = useState('');
  const [score, setScore] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [nextCursor, setNextCursor] = useState<number | null>(null);
  async function refresh(before?: number) {
    const data = await request<{ drawings: Drawing[]; can_review: boolean; next_cursor: number | null }>(before ? `?before=${before}` : '');
    setDrawings(items => before ? [...items, ...data.drawings] : data.drawings); setCanReview(data.can_review); setNextCursor(data.next_cursor);
  }
  useEffect(() => {
    refresh().catch(e => setError(e.message)).finally(() => setLoading(false));
    request<{ models: string[] }>('/vision-models').then(data => { setModels(data.models); setVision(data.models[0] || ''); }).catch(e => setError(e.message));
  }, []);
  async function review(kind: 'ai-review' | 'review') {
    setBusy(true); setError('');
    try {
      const result = await request<Drawing>(`/${active}/${kind}`, kind === 'ai-review' ? { model: vision, safety_model: selected || undefined }
        : { feedback, score: score === '' ? null : Number(score), model: selected || undefined });
      setDrawings(items => items.map(item => item.id === result.id ? result : item)); setFeedback(''); setScore('');
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }
  async function download(id: string, kind: 'image' | 'scene') {
    try {
      const response = await apiFetch(`/api/drawings/${id}/${kind}`);
      if (!response.ok) throw new Error('Could not download this drawing.');
      const url = URL.createObjectURL(await response.blob()); const link = document.createElement('a');
      link.href = url; link.download = kind === 'image' ? 'drawing.png' : 'drawing.excalidraw'; link.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (e) { setError((e as Error).message); }
  }
  const current = drawings.find(item => item.id === active);
  return <div className={styles.page}>
    <h2>Drawing reviews</h2><p>Review visual reasoning alongside the question and the learner’s explanation.</p>
    {error && <p role="alert" className={styles.error}>{error}</p>}
    {loading ? <p role="status">Loading submissions…</p> : !drawings.length ? <p>No drawings submitted yet. Open a question and choose Add a drawing.</p> : <>
      <Select label="Submission" value={active} onChange={value => { setActive(value); setFeedback(''); setScore(''); setError(''); }} disabled={busy}
        placeholder="Choose a drawing" options={drawings.map(item => ({ value: item.id, label: item.question.slice(0, 110), hint: item.status.replaceAll('_', ' ') }))} />
      {nextCursor && <button type="button" disabled={busy} onClick={async () => {
        setBusy(true); try { await refresh(nextCursor); } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
      }}>Load earlier submissions</button>}
      {current && <article className={styles.review} key={current.id}>
        <Markdown>{current.question}</Markdown>
        <p>Submitted {new Date(current.created * 1000).toLocaleString()} · {current.status.replaceAll('_', ' ')}</p>
        <p>Unreviewed learner content. Open only when you are ready to inspect the drawing.</p>
        <details><summary>View submitted drawing</summary><DrawingImage id={current.id} /></details>
        {current.explanation && <><h3>Learner explanation</h3><Markdown>{current.explanation}</Markdown></>}
        <div className={styles.row}><button type="button" onClick={() => download(current.id, 'image')}>Download PNG</button>
          <button type="button" onClick={() => download(current.id, 'scene')}>Download editable drawing</button></div>
        <section><h3>AI feedback</h3><p>Requires an installed vision model. AI feedback does not assign or change an exam score.</p>
          {models.length ? <Select label="Vision model" value={vision} onChange={setVision} disabled={busy}
            options={models.map(model => ({ value: model, label: model }))} /> : <p>No vision model is installed. You can still submit drawings and receive human review. An administrator can install a vision-capable model using Ollama.</p>}
          <button type="button" disabled={busy || !vision} onClick={() => review('ai-review')}>{busy ? 'Review in progress…' : 'Request AI review'}</button>
        </section>
        {canReview && <form onSubmit={event => { event.preventDefault(); review('review'); }}><h3>Human review</h3>
          <label>Reviewer feedback<textarea required maxLength={5000} rows={5} value={feedback} onChange={e => setFeedback(e.target.value)} /></label>
          <label>Optional score out of 100<input type="number" min={0} max={100} step={1} value={score} onChange={e => setScore(e.target.value)} /></label>
          <button disabled={busy || !feedback.trim()}>Submit human review</button>
        </form>}
        {current.reviews.length > 0 && <section><h3>Feedback history</h3>{current.reviews.map((item, index) => <article className={styles.feedback} key={index}>
          <strong>{item.kind === 'ai' ? `AI · ${item.model}` : 'Human reviewer'}{item.score != null ? ` · ${item.score}/100` : ''}</strong>
          {item.observations?.map((text, i) => <p key={i}>Observed: {text}</p>)}<Markdown>{item.feedback}</Markdown>
          {item.improvements?.map((text, i) => <p key={i}>Next: {text}</p>)}
        </article>)}</section>}
      </article>}
    </>}
  </div>;
}
