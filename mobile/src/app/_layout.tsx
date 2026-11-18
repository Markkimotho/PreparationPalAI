import { Manrope_600SemiBold, Manrope_700Bold, Manrope_800ExtraBold } from '@expo-google-fonts/manrope';
import { SourceSans3_400Regular, SourceSans3_600SemiBold, SourceSans3_700Bold } from '@expo-google-fonts/source-sans-3';
import { useFonts } from 'expo-font';
import { DarkTheme, DefaultTheme, Stack, ThemeProvider } from 'expo-router';
import * as SplashScreen from 'expo-splash-screen';
import { StatusBar } from 'expo-status-bar';
import { useEffect } from 'react';
import { useColorScheme } from 'react-native';
import { GestureHandlerRootView } from 'react-native-gesture-handler';

import { Colors, Fonts } from '@/constants/theme';
import { SessionProvider, useSession } from '@/hooks/use-session';

SplashScreen.preventAutoHideAsync();

function Navigator({ fontsReady }: { fontsReady: boolean }) {
  const { state } = useSession();
  const ready = state !== 'loading' && fontsReady;
  useEffect(() => { if (ready) void SplashScreen.hideAsync(); }, [ready]);
  if (!ready) return null;
  return <Stack screenOptions={{ headerShown: false }}>
    <Stack.Protected guard={state === 'signed-in'}>
      <Stack.Screen name="(tabs)" />
      <Stack.Screen name="deck/[id]" options={{ headerShown: true, title: '', headerTransparent: true, headerBackTitle: 'Decks', headerTintColor: '#ffffff' }} />
    </Stack.Protected>
    <Stack.Protected guard={state === 'signed-out'}>
      <Stack.Screen name="sign-in" />
    </Stack.Protected>
  </Stack>;
}

export default function RootLayout() {
  const scheme = useColorScheme();
  // A font that fails to load falls back to the system font rather than blocking the app.
  const [loaded, failed] = useFonts({ Manrope_600SemiBold, Manrope_700Bold, Manrope_800ExtraBold, SourceSans3_400Regular, SourceSans3_600SemiBold, SourceSans3_700Bold });
  const palette = Colors[scheme === 'dark' ? 'dark' : 'light'];
  const base = scheme === 'dark' ? DarkTheme : DefaultTheme;
  const theme = { ...base, colors: { ...base.colors, primary: palette.tint, background: palette.background, card: palette.surface, text: palette.text, border: palette.border },
    fonts: { ...base.fonts, bold: { fontFamily: Fonts.heading, fontWeight: '700' as const }, heavy: { fontFamily: Fonts.display, fontWeight: '800' as const } } };
  return <GestureHandlerRootView style={{ flex: 1 }}>
    <ThemeProvider value={theme}>
      <StatusBar style="auto" />
      <SessionProvider><Navigator fontsReady={loaded || !!failed} /></SessionProvider>
    </ThemeProvider>
  </GestureHandlerRootView>;
}
