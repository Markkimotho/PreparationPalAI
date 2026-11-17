import { useCallback, useEffect, useRef, useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { Body, Button, Card, Field, Heading, Notice, Screen } from '@/components/ui';
import { useSession } from '@/hooks/use-session';
import { useTheme } from '@/hooks/use-theme';
import { deleteRequest, getJson } from '@/utils/api';
import { buy, purchasesAvailable, startPurchases, storePrices } from '@/utils/purchases';

interface Balance { available_credits: number; reserved_credits: number; starter_credits: number }
interface Pack { id: string; price: string; credits: number; available: boolean; product_id?: string | null }
interface Entry { id: number; when: string; label: string; credits: number }

const number = (n: number) => n.toLocaleString('en-US', { maximumFractionDigits: 3 });

export function Account() {
  const colors = useTheme();
  const { signOut } = useSession();
  const [balance, setBalance] = useState<Balance | null>(null);
  const [packs, setPacks] = useState<Pack[]>([]);
  const [prices, setPrices] = useState<Record<string, string>>({});
  const [history, setHistory] = useState<Entry[]>([]);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [buying, setBuying] = useState('');
  const [confirming, setConfirming] = useState(false);
  const [typed, setTyped] = useState('');
  const [deleting, setDeleting] = useState(false);
  const polling = useRef<ReturnType<typeof setTimeout> | null>(null);

  const refresh = useCallback(async () => {
    const [b, h] = await Promise.all([getJson<Balance>('/api/billing/balance'), getJson<{ entries: Entry[] }>('/api/billing/history')]);
    setBalance(b); setHistory(h.entries);
  }, []);

  useEffect(() => {
    (async () => {
      try {
        await refresh();
        const p = await getJson<{ packs: Pack[] }>('/api/billing/packs?channel=store');
        setPacks(p.packs);
        const me = await getJson<{ workspace: string }>('/api/auth/me');
        if (await startPurchases(me.workspace)) {
          setPrices(await storePrices(p.packs.map(x => x.product_id).filter((x): x is string => !!x)));
        }
      } catch (e) {
        setError((e as Error).message);
      }
    })();
    return () => { if (polling.current) clearTimeout(polling.current); };
  }, [refresh]);

  const purchase = async (pack: Pack) => {
    setError(''); setNotice(''); setBuying(pack.id);
    try {
      if ((await buy(pack.product_id!)) === 'purchased') {
        setNotice('Purchase complete. Your credits appear within a few seconds.');
        let tries = 0;
        const poll = () => { tries += 1; void refresh().catch(() => undefined); if (tries < 5) polling.current = setTimeout(poll, 2000); };
        poll();
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBuying('');
    }
  };

  const remove = async () => {
    setError(''); setDeleting(true);
    try {
      await deleteRequest('/api/account');
      await signOut();
    } catch (e) {
      setError((e as Error).message);
      setDeleting(false);
    }
  };

  return <Screen>
    <Heading>Account</Heading>
    <Notice text={notice} />
    <Notice text={error} kind="error" />
    <Card>
      <Heading level={2}>Credits</Heading>
      {balance ? <>
        <Text style={[styles.big, { color: colors.text }]}>{number(balance.available_credits)}</Text>
        {balance.starter_credits > 0 && <Body muted>{`${number(balance.starter_credits)} of these are free starter credits, usable with open models.`}</Body>}
      </> : <Body muted>Loading…</Body>}
    </Card>
    <Card>
      <Heading level={2}>Buy credits</Heading>
      {!purchasesAvailable() ? <Body muted>Buying credits in this app is not available yet. You can top up on the website.</Body> :
        packs.map(p => <Button key={p.id} label={buying === p.id ? 'Opening the store…' : `${number(p.credits)} credits for ${prices[p.product_id ?? ''] ?? p.price}`}
          variant="secondary" disabled={!p.available || !p.product_id || buying !== ''} onPress={() => void purchase(p)} />)}
      <Body muted>A typical quiz uses about 14 credits.</Body>
    </Card>
    <Card>
      <Heading level={2}>History</Heading>
      {history.length === 0 ? <Body muted>No activity yet.</Body> : history.map(e => <View key={e.id} style={styles.row}>
        <Body>{e.label}</Body>
        <Text style={{ color: e.credits > 0 ? colors.success : colors.text, fontVariant: ['tabular-nums'] }}>{e.credits > 0 ? `+${number(e.credits)}` : number(e.credits)}</Text>
      </View>)}
    </Card>
    <Button label="Sign out" variant="secondary" onPress={() => void signOut()} />
    <Card>
      <Heading level={2}>Delete account</Heading>
      {!confirming ? <Button label="Delete my account" variant="danger" onPress={() => setConfirming(true)} /> : <>
        <Body>{`This permanently deletes your notes, documents, decks and practice history, and closes your sign-in.${
          balance && balance.available_credits > 0 ? ` Your ${number(balance.available_credits)} remaining credits will be lost and cannot be refunded.` : ''}`}</Body>
        <Field label="Type DELETE to confirm" value={typed} onChangeText={setTyped} autoCapitalize="characters" autoCorrect={false} />
        <Button label="Permanently delete my account" variant="danger" busy={deleting} disabled={typed !== 'DELETE'} onPress={() => void remove()} />
        <Button label="Cancel" variant="secondary" onPress={() => { setConfirming(false); setTyped(''); }} />
      </>}
    </Card>
  </Screen>;
}

const styles = StyleSheet.create({
  big: { fontSize: 36, fontWeight: '700' },
  row: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', minHeight: 36, gap: 12 },
});
