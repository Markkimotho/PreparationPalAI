import { useRef, useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';

import Markdown from '@/components/markdown';
import { Body, Button, Card, Field, Heading, Notice, Screen, Segmented } from '@/components/ui';
import { useTheme } from '@/hooks/use-theme';
import { stream } from '@/utils/api';
import { pickAndUpload } from '@/utils/upload';

type Mode = 'notes' | 'tutor' | 'code';
interface Message { role: 'you' | 'pal'; text: string; sources?: string[] }

const MODES: Record<Mode, { label: string; path: string; body: (text: string, thread: string) => object; hint: string }> = {
  notes: { label: 'My notes', path: '/api/chat/stream', body: (q, t) => ({ question: q, session_id: t }), hint: 'Ask about the notes you added.' },
  tutor: { label: 'Tutor', path: '/api/agent/stream', body: (m, t) => ({ message: m, thread_id: t }), hint: 'A tutor that can quiz you and explain.' },
  code: { label: 'Code', path: '/api/code-chat/stream', body: (m, t) => ({ message: m, thread_id: t }), hint: 'Debugging, design and trade-offs.' },
};
const newThread = () => Math.random().toString(36).slice(2, 12);

export function Study() {
  const colors = useTheme();
  const [mode, setMode] = useState<Mode>('notes');
  const [threads] = useState<Record<Mode, string>>({ notes: newThread(), tutor: newThread(), code: newThread() });
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const abort = useRef<AbortController | null>(null);

  const send = async () => {
    const text = input.trim();
    if (!text || busy) return;
    setInput(''); setError(''); setBusy(true);
    setMessages(m => [...m, { role: 'you', text }, { role: 'pal', text: '' }]);
    const appendToLast = (change: (m: Message) => Message) => setMessages(all => [...all.slice(0, -1), change(all[all.length - 1])]);
    abort.current = new AbortController();
    try {
      await stream(MODES[mode].path, MODES[mode].body(text, threads[mode]), event => {
        if (event.type === 'token') appendToLast(m => ({ ...m, text: m.text + event.text }));
        if (event.type === 'sources') appendToLast(m => ({ ...m, sources: event.sources.map(s => s.source) }));
        if (event.type === 'error') setError(event.message);
      }, abort.current.signal);
    } catch (e) {
      if ((e as Error).name !== 'AbortError') setError((e as Error).message);
    } finally {
      setBusy(false);
      abort.current = null;
    }
  };

  const upload = async () => {
    setError(''); setNotice('');
    try {
      const queued = await pickAndUpload();
      if (queued) setNotice('Your file is being read. It will be searchable in a minute.');
    } catch (e) {
      setError((e as Error).message);
    }
  };

  return <Screen>
    <Heading>Study</Heading>
    <Segmented options={(Object.keys(MODES) as Mode[]).map(m => ({ value: m, label: MODES[m].label }))} value={mode}
      onChange={m => { setMode(m); setMessages([]); setError(''); }} />
    <Body muted>{MODES[mode].hint}</Body>
    {mode === 'notes' && <Button label="Add notes (PDF or photo)" variant="secondary" onPress={() => void upload()} />}
    {messages.map((m, i) => <Card key={i}>
      <Text style={[styles.who, { color: colors.textSecondary }]}>{m.role === 'you' ? 'You' : 'PrepPal'}</Text>
      {m.role === 'pal' ? (m.text ? <Markdown text={m.text} dom={{ matchContents: true, scrollEnabled: false }} /> :
        <Body muted>{busy && i === messages.length - 1 ? 'Thinking…' : '…'}</Body>) : <Body>{m.text}</Body>}
      {!!m.sources?.length && <Body muted>Sources: {m.sources.join(', ')}</Body>}
    </Card>)}
    <Notice text={notice} />
    <Notice text={error} kind="error" />
    <View style={styles.composer}>
      <Field label="Your question" value={input} onChangeText={setInput} multiline editable={!busy} placeholder="Explain Newton's second law…" />
      {busy ? <Button label="Stop" variant="secondary" onPress={() => abort.current?.abort()} />
        : <Button label="Send" onPress={() => void send()} disabled={!input.trim()} />}
    </View>
  </Screen>;
}

const styles = StyleSheet.create({
  who: { fontSize: 13, fontWeight: '600' },
  composer: { gap: 8 },
});
