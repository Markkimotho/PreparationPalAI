import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ACCENT_COLOURS, type Profile } from '../../api/profile';
import { Avatar } from '../../profile/Avatar';
import { useProfile } from '../../profile/ProfileContext';
import { deleteAccount, getBalance, getHistory, getPacks, startCheckout, type Balance, type HistoryEntry, type Pack } from '../../api/billing';
import { session } from '../../auth/session';
import { openCheckout } from '../../payments/paddle';
import sectionStyles from '../Section.module.css';
import styles from './Account.module.css';

/** Pack tiles cycle through the area colours, as on the phone. */
const TONES = ['blue', 'amber', 'green', 'coral'] as const;
const number = (n: number) => n.toLocaleString('en-US', { maximumFractionDigits: 3 });
const signed = (n: number) => (n > 0 ? `+${number(n)}` : number(n));

export function Account() {
  const [balance, setBalance] = useState<Balance | null>(null);
  const [packs, setPacks] = useState<Pack[]>([]);
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [nextBefore, setNextBefore] = useState<number | null>(null);
  const [unavailable, setUnavailable] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [buying, setBuying] = useState('');
  const [confirming, setConfirming] = useState(false);
  const [typed, setTyped] = useState('');
  const [deleting, setDeleting] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const [b, p, h] = await Promise.all([getBalance(), getPacks(), getHistory()]);
      setBalance(b); setPacks(p.packs); setHistory(h.entries); setNextBefore(h.next_before_id);
    } catch (e) {
      if ((e as { status?: number }).status === 404) setUnavailable(true);
      else setError((e as Error).message);
    }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  const buy = async (pack: Pack) => {
    setError(''); setNotice(''); setBuying(pack.id);
    try {
      const checkout = await startCheckout(pack.id);
      await openCheckout(checkout, () => {
        setNotice('Payment received. Your credits appear within a few seconds.');
        // The payment provider confirms to our server separately; poll briefly for the new balance.
        let tries = 0;
        const poll = () => { tries += 1; void refresh(); if (tries < 5) setTimeout(poll, 2000); };
        poll();
      });
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBuying('');
    }
  };

  const remove = async () => {
    setError(''); setDeleting(true);
    try {
      await deleteAccount();
      await session.signOut();
    } catch (e) {
      setError((e as Error).message);
      setDeleting(false);
    }
  };

  if (unavailable) {
    return <section className={sectionStyles.section}><div className={styles.page}><h1>Account</h1>
      <p>Credits and account settings are available on hosted PreparationPalAI. This installation is self-hosted, so study is free and unmetered.</p>
    </div></section>;
  }

  return <section className={sectionStyles.section}><div className={styles.page}>
    <h1>Account</h1>
    <ProfileCard />
    {notice && <p role="status">{notice}</p>}
    {error && <p role="alert">{error}</p>}

    {/* The balance, as on the phone: a gradient card in the learner's colour. */}
    <div className={styles.hero} aria-label="Credit balance">
      <span className={styles.ring} aria-hidden /><span className={`${styles.ring} ${styles.ringSmall}`} aria-hidden />
      <h2 className={styles.heroLabel}><span aria-hidden>⚡</span> Credits</h2>
      {balance ? <>
        <p className={styles.big}>{number(balance.available_credits)}</p>
        <p className={styles.heroNote}>
          {balance.starter_credits > 0 && `${number(balance.starter_credits)} of these are free starter credits, usable with open models. `}
          {balance.reserved_credits > 0 && `${number(balance.reserved_credits)} are held for a request in progress.`}
        </p>
      </> : <p role="status" className={styles.heroNote}>Loading balance…</p>}
      <p className={styles.heroNote}>A typical quiz uses about 14 credits.</p>
    </div>

    <section className={styles.block} aria-labelledby="buy-credits">
      <h2 id="buy-credits" className={styles.blockTitle}>Buy credits</h2>
      <div className={styles.packs}>
        {packs.map((pack, i) => <button key={pack.id} type="button" className={styles.pack} data-tone={TONES[i % TONES.length]}
          disabled={!pack.available || buying !== ''} onClick={() => void buy(pack)}
          aria-label={buying === pack.id ? 'Opening checkout…' : `Buy ${number(pack.credits)} credits for ${pack.price}`}>
          <span className={styles.packIcon} aria-hidden>⚡</span>
          <span className={styles.packCredits}>{number(pack.credits)}</span>
          <span className={styles.packUnit}>credits</span>
          <span className={styles.price}>{buying === pack.id ? 'Opening…' : pack.price}</span>
        </button>)}
      </div>
      <p className={styles.muted}>One credit is a tenth of a US cent. Prices include tax, handled by our payment provider.</p>
    </section>

    <section className={styles.block} aria-labelledby="history">
      <h2 id="history" className={styles.blockTitle}>History</h2>
      <div className={styles.card}>
      {history.length === 0 ? <p className={styles.muted}>No activity yet.</p> :
        <ul className={styles.history}>{history.map(entry => <li key={entry.id}>
          <span className={`${styles.rowIcon} ${entry.credits > 0 ? styles.rowPlus : ''}`} aria-hidden>{entry.credits > 0 ? '+' : '✦'}</span>
          <span className={styles.rowText}>{entry.label}<span className={styles.muted}>{new Date(entry.when).toLocaleString()}</span></span>
          <span className={entry.credits > 0 ? styles.plus : styles.minus}>{signed(entry.credits)}</span>
        </li>)}</ul>}
      {nextBefore && <button type="button" className={sectionStyles.chip} onClick={async () => {
        const page = await getHistory(nextBefore); setHistory(h => [...h, ...page.entries]); setNextBefore(page.next_before_id);
      }}>Show older activity</button>}
    </div>

    </section>

    <button type="button" className={styles.signOut} onClick={() => void session.signOut()}>Sign out</button>

    <div className={`${styles.card} ${styles.danger}`}>
      <h2>Delete account</h2>
      {!confirming ? <button type="button" className={styles.dangerButton} onClick={() => setConfirming(true)}>Delete my account</button> : <>
        <p>This permanently deletes your notes, documents, decks, practice sessions and drawings, and closes your sign-in.
          {balance && balance.available_credits > 0 && <strong> Your {number(balance.available_credits)} remaining credits will be lost and cannot be refunded.</strong>}
        </p>
        <div className={styles.row}>
          <label htmlFor="confirm-delete">Type DELETE to confirm</label>
          <input id="confirm-delete" className={styles.input} value={typed} onChange={e => setTyped(e.target.value)} autoComplete="off" />
          <button type="button" className={styles.dangerButton} disabled={typed !== 'DELETE' || deleting} onClick={() => void remove()}>
            {deleting ? 'Deleting…' : 'Permanently delete my account'}
          </button>
          <button type="button" className={sectionStyles.chip} onClick={() => { setConfirming(false); setTyped(''); }}>Cancel</button>
        </div>
      </>}
    </div>
  </div></section>;
}

const GOAL_LINE: Record<Profile['goal'], string> = { exam: 'Preparing for an exam', interview: 'Preparing for interviews', understand: 'Learning to understand deeply' };

/** Who the learner is, as the app sees them; the way back into "Make it yours". */
function ProfileCard() {
  const { profile, status, workspace } = useProfile();
  if (status !== 'ready') return null;
  const name = profile.display_name.trim();
  const colour = ACCENT_COLOURS[profile.accent];
  const goal = profile.goal === 'exam' && profile.exam_context.trim() ? `Preparing for ${profile.exam_context.trim()}` : GOAL_LINE[profile.goal];
  return <div className={`${styles.card} ${styles.profile}`} aria-label="Your profile">
    <Avatar seed={`${workspace}:${profile.avatar_seed}`} name={name} size={64} label={name ? `${name}'s avatar` : 'Your avatar'} />
    <div className={styles.profileText}>
      <h2>{name || 'Your profile'}</h2>
      <p className={styles.muted}>{`${goal} · ${profile.level[0].toUpperCase()}${profile.level.slice(1)} · ${profile.daily_goal} a day`}</p>
      {profile.subjects.length > 0 && <ul className={styles.subjects} aria-label="Subjects">
        {profile.subjects.map(s => <li key={s} style={{ background: colour.soft, color: colour.deep }}>{s}</li>)}
      </ul>}
    </div>
    <Link to="/setup?edit=1" className={styles.edit} style={{ borderColor: colour.main, color: colour.deep, background: colour.soft }}>
      {profile.onboarded ? 'Edit profile' : 'Make it yours'}
    </Link>
  </div>;
}
