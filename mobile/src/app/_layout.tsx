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
import { ProfileProvider, useProfile } from '@/hooks/use-profile';
import { SessionProvider, useSession } from '@/hooks/use-session';

SplashScreen.preventAutoHideAsync();

function Navigator({ fontsReady }: { fontsReady: boolean }) {
  const { state } = useSession();
  // The profile is per account: load it only inside a signed-in session.
  return state === 'signed-in'
    ? <ProfileProvider><Routes signedIn fontsReady={fontsReady} /></ProfileProvider>
    : <Routes signedIn={false} fontsReady={fontsReady} loading={state === 'loading'} />;
}

function Routes({ signedIn, fontsReady, loading = false }: { signedIn: boolean; fontsReady: boolean; loading?: boolean }) {
  const { profile, status } = useProfile();
  const ready = fontsReady && !loading && (!signedIn || status !== 'loading');
  useEffect(() => { if (ready) void SplashScreen.hideAsync(); }, [ready]);
  if (!ready) return null;
  // A learner who has not made the app theirs yet starts there (if the profile could not be loaded,
  // offline on a first launch, they get the app with defaults rather than a blocked screen).
  const needsSetup = signedIn && status === 'ready' && !profile.onboarded;
  return <Stack screenOptions={{ headerShown: false }}>
    <Stack.Protected guard={signedIn && !needsSetup}>
      <Stack.Screen name="(tabs)" />
      <Stack.Screen name="deck/[id]" options={{ headerShown: true, title: '', headerTransparent: true, headerBackTitle: 'Decks', headerTintColor: '#ffffff' }} />
    </Stack.Protected>
    <Stack.Protected guard={signedIn}>
      <Stack.Screen name="setup" options={{ presentation: needsSetup ? 'card' : 'modal', gestureEnabled: !needsSetup }} />
    </Stack.Protected>
    <Stack.Protected guard={!signedIn}>
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
