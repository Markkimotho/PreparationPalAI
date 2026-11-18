import { useLocalSearchParams } from 'expo-router';

import { DeckStudy } from '@/screens/deck';

export default function DeckRoute() {
  // Development builds only (screenshots, review): `face=back` opens the first card flipped,
  // `preview=strong|learning` opens the end-of-deck summary.
  const { id, face, preview } = useLocalSearchParams<{ id: string; face?: string; preview?: string }>();
  const summary = __DEV__ && (preview === 'strong' || preview === 'learning') ? preview : undefined;
  return <DeckStudy key={`${id}-${face ?? ''}-${preview ?? ''}`} id={id} startFlipped={__DEV__ && face === 'back'} preview={summary} />;
}
