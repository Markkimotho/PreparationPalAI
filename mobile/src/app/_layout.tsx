import { DarkTheme, DefaultTheme, Stack, ThemeProvider } from 'expo-router';
import * as SplashScreen from 'expo-splash-screen';
import { useEffect } from 'react';
import { useColorScheme } from 'react-native';

import { SessionProvider, useSession } from '@/hooks/use-session';

SplashScreen.preventAutoHideAsync();

function Navigator() {
  const { state } = useSession();
  useEffect(() => { if (state !== 'loading') void SplashScreen.hideAsync(); }, [state]);
  if (state === 'loading') return null;
  return <Stack screenOptions={{ headerShown: false }}>
    <Stack.Protected guard={state === 'signed-in'}>
      <Stack.Screen name="(tabs)" />
      <Stack.Screen name="deck/[id]" options={{ headerShown: true, title: 'Study deck', headerBackTitle: 'Decks' }} />
    </Stack.Protected>
    <Stack.Protected guard={state === 'signed-out'}>
      <Stack.Screen name="sign-in" />
    </Stack.Protected>
  </Stack>;
}

export default function RootLayout() {
  const scheme = useColorScheme();
  return <ThemeProvider value={scheme === 'dark' ? DarkTheme : DefaultTheme}>
    <SessionProvider><Navigator /></SessionProvider>
  </ThemeProvider>;
}
