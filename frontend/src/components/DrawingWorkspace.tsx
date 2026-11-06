import { lazy, Suspense, useCallback, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { apiFetch } from '../api/access';
import type { DrawingSnapshot } from './DrawingCanvas';
import styles from './DrawingWorkspace.module.css';

const DrawingCanvas = lazy(() => import('./DrawingCanvas'));
export function needsDrawing(question: string) {
  return /\b(draw|sketch|plot|annotate|construct|illustrate|label)\b.{0,90}\b(diagram|graph|circuit|structure|curve|vector|forces?|cell|molecule|shape|tree|network|ray|path|axes|field|distribution|construction|schematic|flowchart)\b/i.test(question)
    || /^\s*(plot|sketch)\s+.*(?:=|\bfunction\b)/i.test(question)
    || /\b(draw|sketch)\s+(?:a|an|the|your)\s+(?:labelled|labeled|free.body)/i.test(question);
}
interface Props { question: string; required?: boolean; brief?: string; sessionId?: string; learner?: string; index?: number; model?: string }

export function DrawingWorkspace({ question, required = false, brief, sessionId, learner, index, model }: Props) {
  const suggested = required || needsDrawing(question);
  const [open, setOpen] = useState(suggested);
  const [hasOpened, setHasOpened] = useState(suggested);
  const [explanation, setExplanation] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [submission, setSubmission] = useState('');
  const snapshot = useRef<{ question: string; take: () => Promise<DrawingSnapshot> } | null>(null);
  const [readyQuestion, setReadyQuestion] = useState('');
  const onReady = useCallback((take: () => Promise<DrawingSnapshot>) => {
    snapshot.current = { question, take }; setReadyQuestion(question);
  }, [question]);
  useEffect(() => { setOpen(suggested); setHasOpened(suggested); setExplanation(''); setSubmission(''); setError(''); }, [question, suggested]);
  async function submit() {
    if (!snapshot.current || snapshot.current.question !== question) return;
    setBusy(true); setError('');
    try {
      const drawing = await snapshot.current.take();
      const response = await apiFetch('/api/drawings', { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...drawing, question, explanation, model,
          session_id: sessionId, learner, index }),
      });
      const body = await response.json();
      if (!response.ok) throw new Error(typeof body.detail === 'string' ? body.detail : 'Could not submit the drawing.');
      setSubmission(body.id);
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }
  async function saveLocal(kind: 'png' | 'scene') {
    if (!snapshot.current || snapshot.current.question !== question) return;
    setError('');
    try {
      const drawing = await snapshot.current.take();
      const link = document.createElement('a');
      const url = kind === 'png' ? drawing.image : URL.createObjectURL(new Blob([JSON.stringify(drawing.scene)], { type: 'application/json' }));
      link.href = url; link.download = kind === 'png' ? 'drawing.png' : 'drawing.excalidraw'; link.click();
      if (kind === 'scene') window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (e) { setError((e as Error).message); }
  }
  return <section className={styles.workspace} aria-label="Drawing answer">
    <button className={styles.toggle} type="button" aria-expanded={open} onClick={() => { setHasOpened(true); setOpen(!open); }}>
      {open ? 'Hide drawing workspace' : suggested ? 'Open drawing workspace' : 'Add a drawing'}
    </button>
    {hasOpened && <div hidden={!open}>
      <p>{brief || 'Use shapes, arrows, labels or freehand drawing to explain your answer.'}</p>
      <p>Drawings are reviewed separately from written-answer scores. Your work stays in this workspace.</p>
      <div className={styles.canvas} key={question}><Suspense fallback={<p role="status">Loading drawing tools…</p>}>
        <DrawingCanvas onReady={onReady} onDirty={() => setSubmission('')} />
      </Suspense></div>
      <label>Explain your drawing<textarea rows={3} maxLength={10000} value={explanation}
        onChange={e => { setExplanation(e.target.value); setSubmission(''); }} placeholder="Describe labels, assumptions, units, and anything the reviewer should check." /></label>
      <button className={styles.submit} type="button" disabled={busy || readyQuestion !== question} onClick={submit}>{busy ? 'Saving drawing…' : 'Submit drawing for review'}</button>
      <div className={styles.downloads}><button type="button" disabled={busy || readyQuestion !== question} onClick={() => saveLocal('png')}>Save PNG</button>
        <button type="button" disabled={busy || readyQuestion !== question} onClick={() => saveLocal('scene')}>Save editable drawing</button></div>
      {submission && <p role="status">Drawing saved. <Link to="/drawings">Open drawing reviews →</Link></p>}
      {error && <p role="alert">{error}</p>}
    </div>}
  </section>;
}
