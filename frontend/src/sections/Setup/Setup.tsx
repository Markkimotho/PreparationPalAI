/**
 * "Make it yours" on the web: the same five steps as the phone app (name, goal, subjects and level,
 * daily goal, look). Shown after sign-in until the profile is set up, and at /setup?edit=1 to edit.
 * Steps enter from the side they come from (240ms strong ease-out; none under reduced motion), focus
 * moves to each step's heading for keyboard and screen-reader users, and Enter continues.
 */
import { useEffect, useRef, useState, type FormEvent } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { ACCENT_COLOURS, type Accent, type Profile } from '../../api/profile';
import { Avatar } from '../../profile/Avatar';
import { newSeed } from '../../profile/avatarSpec';
import { useProfile } from '../../profile/ProfileContext';
import styles from './Setup.module.css';

export const POPULAR_SUBJECTS = ['Biology', 'Chemistry', 'Physics', 'Mathematics', 'Computer science', 'Economics',
  'Business', 'History', 'Medicine', 'Law', 'English', 'Engineering'];
const GOALS: { value: Profile['goal']; title: string; detail: string }[] = [
  { value: 'exam', title: 'Ace an exam', detail: 'Recall, exam-style questions and timing.' },
  { value: 'interview', title: 'Nail interviews', detail: 'Explain clearly and handle follow-ups.' },
  { value: 'understand', title: 'Understand deeply', detail: 'Intuition first, then the detail.' },
];
const PACES = [{ value: 5, title: 'Light' }, { value: 10, title: 'Steady' }, { value: 20, title: 'Focused' }, { value: 40, title: 'Intense' }];
const LEVELS: Profile['level'][] = ['beginner', 'intermediate', 'advanced'];
const ACCENTS: Accent[] = ['blue', 'amber', 'green', 'coral'];
const STEPS = 5;

export function Setup() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const editing = params.get('edit') === '1';
  const { profile, workspace, save } = useProfile();
  const [draft, setDraft] = useState<Profile>(() => ({ ...profile, avatar_seed: profile.avatar_seed || newSeed() }));
  const [step, setStep] = useState(0);
  const [direction, setDirection] = useState<'forward' | 'back'>('forward');
  const [custom, setCustom] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [flipping, setFlipping] = useState(false);
  const heading = useRef<HTMLHeadingElement>(null);
  const first = useRef(true);
  const set = (changes: Partial<Profile>) => setDraft(d => ({ ...d, ...changes }));
  const colour = ACCENT_COLOURS[draft.accent];

  useEffect(() => {                                 // move focus to the new step (not on first paint)
    if (first.current) { first.current = false; return; }
    heading.current?.focus();
  }, [step]);
  useEffect(() => { document.title = `${editing ? 'Edit profile' : 'Make it yours'} · PreparationPalAI`; }, [editing]);
  useEffect(() => {                                 // first-time setup hands over once the profile is set up
    if (!editing && profile.onboarded) navigate('/prepare', { replace: true });
  }, [editing, profile.onboarded, navigate]);

  const go = (to: number) => { setDirection(to > step ? 'forward' : 'back'); setStep(to); };
  const canContinue = step === 0 ? draft.display_name.trim().length > 0 : step === 2 ? draft.subjects.length > 0 : true;
  const finish = async (asIs = false) => {
    setBusy(true); setError('');
    try {
      await save({ ...(asIs ? profile : draft), avatar_seed: draft.avatar_seed, onboarded: true });
      if (editing) navigate('/account');
    } catch (e) {
      setError((e as Error).message || 'Could not save. Please retry.');
      setBusy(false);
    }
  };
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!canContinue || busy) return;
    if (step < STEPS - 1) go(step + 1); else void finish();
  };
  const has = (s: string) => draft.subjects.some(x => x.toLowerCase() === s.toLowerCase());
  const toggle = (s: string) => set({
    subjects: has(s) ? draft.subjects.filter(x => x.toLowerCase() !== s.toLowerCase()) : draft.subjects.length < 6 ? [...draft.subjects, s] : draft.subjects,
  });
  const addCustom = () => { const s = custom.trim().slice(0, 60); if (s) { if (!has(s)) toggle(s); setCustom(''); } };
  const shuffle = () => {
    if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) { set({ avatar_seed: newSeed() }); return; }
    setFlipping(true);
    window.setTimeout(() => set({ avatar_seed: newSeed() }), 210);        // swap while the avatar is edge-on
    window.setTimeout(() => setFlipping(false), 420);
  };
  const seed = `${workspace}:${draft.avatar_seed}`;
  const name = draft.display_name.trim();

  const titles = [
    ['What should we call you?', 'It’s how PrepPal greets you.'],
    [`What are you working toward${name ? `, ${name}` : ''}?`, 'Your tutor adapts its questions and feedback to this.'],
    ['What are you studying?', 'Pick up to six. Your answers, quizzes and cards start here.'],
    ['How much each day?', 'Answers, cards and questions all count. You can change this any time.'],
    ['Pick your look', 'Your colour and avatar follow you across the app, on every device.'],
  ];

  return <main className={styles.page} style={{ '--setup-accent': colour.main, '--setup-soft': colour.soft, '--setup-deep': colour.deep } as React.CSSProperties}>
    <form className={styles.shell} onSubmit={submit} noValidate>
      <div className={styles.top}>
        {step > 0 ? <button type="button" className={styles.ghost} onClick={() => go(step - 1)}>‹ Back</button>
          : editing ? <button type="button" className={styles.ghost} onClick={() => navigate('/account')}>Cancel</button> : <span />}
        <div className={styles.progress} role="progressbar" aria-label={`Step ${step + 1} of ${STEPS}`} aria-valuemin={1} aria-valuemax={STEPS} aria-valuenow={step + 1}>
          <div className={styles.progressFill} style={{ width: `${((step + 1) / STEPS) * 100}%` }} />
        </div>
        {!editing ? <button type="button" className={styles.ghost} onClick={() => void finish(true)} disabled={busy}>Skip for now</button> : <span />}
      </div>

      <section key={step} className={`${styles.step} ${direction === 'forward' ? styles.fromRight : styles.fromLeft}`} aria-labelledby="setup-title">
        {step === 0 && <div className={styles.hero}><Avatar seed={seed} name={name} size={104} /></div>}
        <h1 id="setup-title" ref={heading} tabIndex={-1} className={styles.title}>{titles[step][0]}</h1>
        <p className={styles.sub}>{titles[step][1]}</p>

        {step === 0 && <><label htmlFor="setup-name" className={styles.hidden}>Your name</label>
          <input id="setup-name" className={styles.input} value={draft.display_name} maxLength={40} autoComplete="given-name"
            autoFocus={!editing} placeholder="Your first name" onChange={e => set({ display_name: e.target.value })} /></>}

        {step === 1 && <div role="radiogroup" aria-label="Your goal" className={styles.list}>
          {GOALS.map(g => <button key={g.value} type="button" role="radio" aria-checked={draft.goal === g.value}
            className={styles.choice} onClick={() => set({ goal: g.value })}>
            <span><strong>{g.title}</strong><span className={styles.detail}>{g.detail}</span></span>
            <span className={styles.radio} aria-hidden />
          </button>)}
        </div>}

        {step === 2 && <>
          <div className={styles.chips} role="group" aria-label="Subjects">
            {[...POPULAR_SUBJECTS, ...draft.subjects.filter(s => !POPULAR_SUBJECTS.some(p => p.toLowerCase() === s.toLowerCase()))].map(s =>
              <button key={s} type="button" aria-pressed={has(s)} className={styles.chip} onClick={() => toggle(s)}>{has(s) ? '✓ ' : ''}{s}</button>)}
          </div>
          <div className={styles.addRow}>
            <label htmlFor="setup-custom" className={styles.hidden}>Add your own subject</label>
            <input id="setup-custom" className={styles.input} value={custom} maxLength={60} placeholder="Add your own…"
              onChange={e => setCustom(e.target.value)} onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); addCustom(); } }} />
            <button type="button" className={styles.secondary} onClick={addCustom} disabled={!custom.trim()}>Add</button>
          </div>
          <span className={styles.label} id="setup-level">Your level</span>
          <div role="radiogroup" aria-labelledby="setup-level" className={styles.segmented}>
            {LEVELS.map(l => <button key={l} type="button" role="radio" aria-checked={draft.level === l} onClick={() => set({ level: l })}>
              {l[0].toUpperCase() + l.slice(1)}</button>)}
          </div>
          {draft.goal === 'exam' && <><label htmlFor="setup-exam" className={styles.label}>Which exam, and when?</label>
            <input id="setup-exam" className={styles.input} value={draft.exam_context} maxLength={200} placeholder="KCSE, November 2027"
              onChange={e => set({ exam_context: e.target.value })} /></>}
        </>}

        {step === 3 && <div role="radiogroup" aria-label="Daily goal" className={styles.paces}>
          {PACES.map(p => <button key={p.value} type="button" role="radio" aria-checked={draft.daily_goal === p.value}
            aria-label={`${p.title}, ${p.value} a day`} className={styles.pace} onClick={() => set({ daily_goal: p.value })}>
            <span className={styles.paceValue}>{p.value}</span><span>{p.title}</span>
          </button>)}
        </div>}

        {step === 4 && <>
          <div className={styles.lookRow}>
            <div className={`${styles.flipper} ${flipping ? styles.flip : ''}`}>
              <Avatar seed={seed} name={name} size={128} label={`Your avatar${name ? `, ${name}` : ''}`} />
            </div>
            <button type="button" className={styles.secondary} onClick={shuffle}>Shuffle avatar</button>
          </div>
          <div role="radiogroup" aria-label="Your colour" className={styles.swatches}>
            {ACCENTS.map(a => <button key={a} type="button" role="radio" aria-checked={draft.accent === a} aria-label={`${a} colour`}
              className={styles.swatch} style={{ background: ACCENT_COLOURS[a].main }} onClick={() => set({ accent: a })} />)}
          </div>
        </>}
      </section>

      {error && <p role="alert" className={styles.error}>{error}</p>}
      <button type="submit" className={styles.primary} disabled={!canContinue || busy}>
        {step < STEPS - 1 ? 'Continue' : busy ? 'Saving…' : editing ? 'Save changes' : 'Start learning'}
      </button>
    </form>
  </main>;
}
