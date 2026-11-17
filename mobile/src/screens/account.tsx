import { LinearGradient } from 'expo-linear-gradient';
import { useCallback, useEffect, useRef, useState } from 'react';
import { ActivityIndicator, StyleSheet, Text, View } from 'react-native';

import { Body, Button, Card, Field, Icon, Notice, PressableScale, Screen } from '@/components/ui';
import { Fonts, Radius } from '@/constants/theme';
import { useSession } from '@/hooks/use-session';
import { useTheme } from '@/hooks/use-theme';
import { deleteRequest, getJson } from '@/utils/api';
import { haptics } from '@/utils/haptics';
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
        haptics.success();
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

  return <Screen title="Account" accent="blue">
    <Notice text={notice} />
    <Notice text={error} kind="error" />

    <View style={[styles.heroShadow, { shadowColor: colors.blueDeep, backgroundColor: colors.blueDeep }]}>
      <LinearGradient colors={[colors.blue, colors.blueDeep]} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={styles.hero}>
        <View style={[styles.ring, styles.ringBig]} /><View style={[styles.ring, styles.ringSmall]} />
        <View style={styles.heroLabel}>
          <Icon name={{ ios: 'bolt.fill', android: 'bolt' }} size={16} color="#ffffff" />
          <Text accessibilityRole="header" style={styles.heroLabelText}>Credits</Text>
        </View>
        {balance ? <>
          <Text style={styles.balance}>{number(balance.available_credits)}</Text>
          {balance.starter_credits > 0 && <Text style={styles.heroNote}>{`${number(balance.starter_credits)} of these are free starter credits, usable with open models.`}</Text>}
        </> : <ActivityIndicator color="#ffffff" style={styles.loading} />}
        <Text style={styles.heroNote}>A typical quiz uses about 14 credits.</Text>
      </LinearGradient>
    </View>

    <Text accessibilityRole="header" style={[styles.section, { color: colors.text }]}>Buy credits</Text>
    {!purchasesAvailable()
      ? <Card><Body muted>Buying credits in this app is not available yet. You can top up on the website.</Body></Card>
      : <View style={styles.packs}>
        {packs.map((p, i) => {
          const price = prices[p.product_id ?? ''] ?? p.price;
          const label = buying === p.id ? 'Opening the store…' : `${number(p.credits)} credits for ${price}`;
          const accent = (['blue', 'amber', 'green', 'coral'] as const)[i % 4];
          return <View key={p.id} style={styles.packSlot}>
            <PressableScale accessibilityLabel={label} disabled={!p.available || !p.product_id || buying !== ''} onPress={() => void purchase(p)}
              style={[styles.pack, { backgroundColor: colors.surface, borderColor: colors.border, shadowColor: colors.shadow }, (!p.available || !p.product_id) && styles.dim]}>
              <View style={[styles.packIcon, { backgroundColor: colors[`${accent}Soft`] }]}>
                {buying === p.id ? <ActivityIndicator color={colors[accent]} /> : <Icon name={{ ios: 'bolt.fill', android: 'bolt' }} size={18} color={colors[accent]} />}
              </View>
              <Text style={[styles.packCredits, { color: colors.text }]}>{number(p.credits)}</Text>
              <Text style={[styles.packUnit, { color: colors.textSecondary }]}>credits</Text>
              <View style={[styles.price, { backgroundColor: colors[`${accent}Soft`] }]}><Text style={[styles.priceText, { color: colors[`${accent}Deep`] }]}>{price}</Text></View>
            </PressableScale>
          </View>;
        })}
      </View>}

    <Text accessibilityRole="header" style={[styles.section, { color: colors.text }]}>History</Text>
    <Card style={styles.history}>
      {history.length === 0 ? <Body muted>No activity yet.</Body> : history.map((e, i) => <View key={e.id}
        style={[styles.row, i > 0 && { borderTopColor: colors.border, borderTopWidth: StyleSheet.hairlineWidth }]}>
        <View style={[styles.rowIcon, { backgroundColor: e.credits > 0 ? colors.successSoft : colors.backgroundElement }]}>
          <Icon name={e.credits > 0 ? { ios: 'plus', android: 'add' } : { ios: 'sparkles', android: 'auto_awesome' }} size={14}
            color={e.credits > 0 ? colors.success : colors.textSecondary} />
        </View>
        <Text style={[styles.rowLabel, { color: colors.text }]}>{e.label}</Text>
        <Text style={[styles.amount, { color: e.credits > 0 ? colors.success : colors.text }]}>{e.credits > 0 ? `+${number(e.credits)}` : number(e.credits)}</Text>
      </View>)}
    </Card>

    <Button label="Sign out" variant="secondary" icon={{ ios: 'rectangle.portrait.and.arrow.right', android: 'logout' }} onPress={() => void signOut()} />

    <Card style={[styles.danger, { borderColor: colors.dangerSoft }]}>
      <Text accessibilityRole="header" style={[styles.dangerTitle, { color: colors.danger }]}>Delete account</Text>
      {!confirming ? <Button label="Delete my account" variant="danger" icon={{ ios: 'trash', android: 'delete' }} onPress={() => setConfirming(true)} /> : <>
        <Body>{`This permanently deletes your notes, documents, decks and practice history, and closes your sign-in.${
          balance && balance.available_credits > 0 ? ` Your ${number(balance.available_credits)} remaining credits will be lost and cannot be refunded.` : ''}`}</Body>
        <Field label="Type DELETE to confirm" value={typed} onChangeText={setTyped} autoCapitalize="characters" autoCorrect={false} />
        <Button label="Permanently delete my account" variant="danger" busy={deleting} disabled={typed !== 'DELETE'} onPress={() => void remove()} />
        <Button label="Cancel" variant="ghost" compact onPress={() => { setConfirming(false); setTyped(''); }} />
      </>}
    </Card>
  </Screen>;
}

const styles = StyleSheet.create({
  heroShadow: { borderRadius: Radius.xl, shadowOpacity: 0.3, shadowRadius: 20, shadowOffset: { width: 0, height: 10 }, elevation: 5 },
  hero: { borderRadius: Radius.xl, padding: 22, gap: 6, overflow: 'hidden' },
  ring: { position: 'absolute', borderRadius: 999, borderWidth: 18, borderColor: 'rgba(255,255,255,0.08)' },
  ringBig: { width: 220, height: 220, right: -70, top: -90 },
  ringSmall: { width: 120, height: 120, right: 40, bottom: -70 },
  heroLabel: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  heroLabelText: { fontFamily: Fonts.bodyBold, fontSize: 15, color: 'rgba(255,255,255,0.9)', letterSpacing: 0.3 },
  balance: { fontFamily: Fonts.display, fontSize: 52, color: '#ffffff', letterSpacing: -2, fontVariant: ['tabular-nums'] },
  heroNote: { fontFamily: Fonts.body, fontSize: 15, lineHeight: 21, color: 'rgba(255,255,255,0.85)' },
  loading: { alignSelf: 'flex-start', marginVertical: 18 },
  section: { fontFamily: Fonts.heading, fontSize: 20, letterSpacing: -0.3, marginTop: 6 },
  packs: { flexDirection: 'row', flexWrap: 'wrap', marginHorizontal: -6 },
  packSlot: { width: '50%', padding: 6 },
  pack: { borderRadius: Radius.lg, padding: 16, gap: 2, borderWidth: StyleSheet.hairlineWidth, shadowOpacity: 0.06, shadowRadius: 12, shadowOffset: { width: 0, height: 6 } },
  packIcon: { width: 34, height: 34, borderRadius: 11, alignItems: 'center', justifyContent: 'center', marginBottom: 8 },
  packCredits: { fontFamily: Fonts.display, fontSize: 26, letterSpacing: -0.8, fontVariant: ['tabular-nums'] },
  packUnit: { fontFamily: Fonts.bodySemi, fontSize: 14 },
  price: { alignSelf: 'flex-start', marginTop: 10, paddingHorizontal: 10, paddingVertical: 4, borderRadius: 999 },
  priceText: { fontFamily: Fonts.bodyBold, fontSize: 14 },
  dim: { opacity: 0.5 },
  history: { paddingVertical: 6, gap: 0 },
  row: { flexDirection: 'row', alignItems: 'center', gap: 12, minHeight: 52 },
  rowIcon: { width: 28, height: 28, borderRadius: 9, alignItems: 'center', justifyContent: 'center' },
  rowLabel: { flex: 1, fontFamily: Fonts.body, fontSize: 16 },
  amount: { fontFamily: Fonts.bodyBold, fontSize: 16, fontVariant: ['tabular-nums'] },
  danger: { borderWidth: 1 },
  dangerTitle: { fontFamily: Fonts.heading, fontSize: 17 },
});
