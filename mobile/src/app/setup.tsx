import { useLocalSearchParams } from 'expo-router';

import { Setup } from '@/screens/setup';

export default function SetupRoute() {
  const { edit } = useLocalSearchParams<{ edit?: string }>();
  return <Setup editing={edit === '1'} />;
}
