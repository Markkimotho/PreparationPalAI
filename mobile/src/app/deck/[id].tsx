import { useLocalSearchParams } from 'expo-router';

import { DeckStudy } from '@/screens/deck';

export default function DeckRoute() {
  // `face=back` opens the first card flipped, in development builds only (screenshots, review).
  const { id, face } = useLocalSearchParams<{ id: string; face?: string }>();
  return <DeckStudy key={`${id}-${face ?? ''}`} id={id} startFlipped={__DEV__ && face === 'back'} />;
}
