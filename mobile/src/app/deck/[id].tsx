import { useLocalSearchParams } from 'expo-router';

import { DeckStudy } from '@/screens/deck';

export default function DeckRoute() {
  const { id } = useLocalSearchParams<{ id: string }>();
  return <DeckStudy id={id} />;
}
