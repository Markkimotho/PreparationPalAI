import { useState } from 'react';
import { apiFetch } from '../api/access';
import { useModelContext } from '../context/ModelContext';
import { Select } from './Select';
import styles from './StudyExport.module.css';

interface Props {
  title?: string;
  questions?: unknown[];
  sessionId?: string;
  learner?: string;
  deckId?: string;
  answersAvailable?: boolean;
}

export function StudyExport({ title = 'Study practice', questions, sessionId, learner, deckId, answersAvailable = true }: Props) {
  const { selected } = useModelContext();
  const [kind, setKind] = useState('exam');
  const [format, setFormat] = useState('pdf');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  async function download() {
    setBusy(true); setError('');
    try {
      const response = await apiFetch('/api/exports/study', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title, kind, format, questions, session_id: sessionId,
          learner, deck_id: deckId, model: selected || undefined }),
      });
      if (!response.ok) {
        const body = await response.json();
        throw new Error(typeof body.detail === 'string' ? body.detail : 'Could not export this study material.');
      }
      const url = URL.createObjectURL(await response.blob());
      const link = document.createElement('a');
      link.href = url; link.download = `study-${kind}.${format === 'pdf' ? 'pdf' : 'md'}`;
      document.body.appendChild(link); link.click(); link.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }
  return <section className={styles.export} aria-label="Export study material">
    <div className={styles.controls}>
      <Select label="Study pack" value={kind} onChange={setKind} disabled={busy} options={[
        { value: 'exam', label: 'Exam' }, { value: 'worksheet', label: 'Written worksheet' },
        { value: 'checklist', label: 'Revision checklist' },
        ...(answersAvailable ? [{ value: 'answers', label: 'Separate answer key' }] : []),
      ]} />
      <Select label="File type" value={format} onChange={setFormat} disabled={busy} options={[
        { value: 'pdf', label: 'Fillable PDF' }, { value: 'markdown', label: 'Markdown' },
      ]} />
      <button type="button" disabled={busy} onClick={download}>{busy ? 'Checking & preparing…' : 'Download'}</button>
    </div>
    <p>Exams and worksheets leave answers blank. PDF fields can be filled in a PDF reader, saved, or printed.</p>
    {error && <p role="alert">{error}</p>}
  </section>;
}
