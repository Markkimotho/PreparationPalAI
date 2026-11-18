import { NativeTabs } from 'expo-router/native-tabs';

import { useAccent } from '@/hooks/use-profile';
import { useTheme } from '@/hooks/use-theme';

const TABS = [
  { name: 'index', label: 'Study', sf: 'text.bubble', md: 'chat' },
  { name: 'quiz', label: 'Quiz', sf: 'checklist', md: 'quiz' },
  { name: 'cards', label: 'Cards', sf: 'rectangle.stack', md: 'style' },
  { name: 'coach', label: 'Coach', sf: 'figure.mind.and.body', md: 'school' },
  { name: 'account', label: 'Account', sf: 'person.crop.circle', md: 'account_circle' },
] as const;

export default function TabsLayout() {
  const colors = useTheme();
  const accent = useAccent();                     // the learner's own colour
  // Tab switches never animate (they are peers, used dozens of times a session): the platform's own tab bar.
  return <NativeTabs tintColor={colors[accent]} indicatorColor={colors[`${accent}Soft`]} labelStyle={{ selected: { color: colors[accent] } }}>
    {TABS.map(t => <NativeTabs.Trigger key={t.name} name={t.name}>
      <NativeTabs.Trigger.Label>{t.label}</NativeTabs.Trigger.Label>
      <NativeTabs.Trigger.Icon sf={t.sf} md={t.md} />
    </NativeTabs.Trigger>)}
  </NativeTabs>;
}
