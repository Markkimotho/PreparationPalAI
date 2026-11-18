/** One-tap starting points from the learner's own subjects (nothing renders without a profile). */
import { ScrollView, StyleSheet, Text } from 'react-native';

import { PressableScale } from '@/components/ui';
import { accentColors, Fonts, Radius, type Accent } from '@/constants/theme';
import { useProfile } from '@/hooks/use-profile';
import { useTheme } from '@/hooks/use-theme';
import { topicChips } from '@/utils/suggestions';

export function TopicChips({ value, onPick, accent }: { value: string; onPick: (topic: string) => void; accent: Accent }) {
  const colors = useTheme();
  const { profile } = useProfile();
  const topics = topicChips(profile);
  if (topics.length === 0) return null;
  const a = accentColors(colors, accent);
  return <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.row} keyboardShouldPersistTaps="handled">
    {topics.map(t => {
      const on = value.trim().toLowerCase() === t.toLowerCase();
      return <PressableScale key={t} onPress={() => onPick(t)} accessibilityLabel={`Use topic ${t}`} accessibilityState={{ selected: on }}
        style={[styles.chip, { backgroundColor: on ? a.main : a.soft }]}>
        <Text style={[styles.text, { color: on ? '#ffffff' : a.deep }]}>{t}</Text>
      </PressableScale>;
    })}
  </ScrollView>;
}

const styles = StyleSheet.create({
  row: { gap: 8, paddingVertical: 2 },
  chip: { minHeight: 36, paddingHorizontal: 14, borderRadius: Radius.pill, justifyContent: 'center' },
  text: { fontFamily: Fonts.bodyBold, fontSize: 14 },
});
