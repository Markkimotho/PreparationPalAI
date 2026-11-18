/**
 * Brand palette: the web app and docs family (paper, ink, navy, gold, the logo's green and mint),
 * brightened for a phone. Every study area has its own accent so each tab feels distinct:
 * Study is blue (the web's navy, lifted), Quiz is amber (the docs' gold), Cards is green (the logo),
 * Coach is coral (the web's red, warmed). `soft` tints are backgrounds; `deep` ends gradients.
 */
export const Colors = {
  light: {
    text: '#1f262b', textSecondary: '#5d666c', textFaint: '#8a9298',
    background: '#fbfaf6', surface: '#ffffff', backgroundElement: '#f3f1ea', backgroundSelected: '#e9e6dc',
    border: '#e8e5dc', shadow: '#1f262b',
    tint: '#2f6fe4', onTint: '#ffffff',
    blue: '#2f6fe4', blueDeep: '#1d4f9f', blueSoft: '#e3edff',
    amber: '#f29d16', amberDeep: '#c96f05', amberSoft: '#fff1d6',
    green: '#1fa774', greenDeep: '#156b4d', greenSoft: '#dbf4e8',
    coral: '#f8624d', coralDeep: '#c63c2b', coralSoft: '#ffe6e1',
    brand: '#194f3c', mint: '#c9e6bc',
    danger: '#d92d20', dangerSoft: '#fdebe9', success: '#16a06a', successSoft: '#ddf5ea',
  },
  dark: {
    text: '#eef1f4', textSecondary: '#a6b0b8', textFaint: '#76818a',
    background: '#10151a', surface: '#19212a', backgroundElement: '#212b35', backgroundSelected: '#2b3742',
    border: '#2b3640', shadow: '#000000',
    tint: '#5c9bff', onTint: '#ffffff',
    blue: '#5c9bff', blueDeep: '#2f6fe4', blueSoft: '#1a2c4a',
    amber: '#ffb648', amberDeep: '#e08a0e', amberSoft: '#3a2b12',
    green: '#3fd29a', greenDeep: '#1fa774', greenSoft: '#143528',
    coral: '#ff8572', coralDeep: '#f8624d', coralSoft: '#3d211d',
    brand: '#c9e6bc', mint: '#c9e6bc',
    danger: '#ff7a6b', dangerSoft: '#3d1f1c', success: '#3fd29a', successSoft: '#143528',
  },
} as const;

export type Palette = (typeof Colors)['light'] | (typeof Colors)['dark'];
export type Accent = 'blue' | 'amber' | 'green' | 'coral';

export function accentColors(colors: Palette, accent: Accent) {
  return { main: colors[accent], deep: colors[`${accent}Deep`], soft: colors[`${accent}Soft`] };
}

/** Manrope for headings and Source Sans 3 for text, the same pair as the web app. Loaded in the root layout. */
export const Fonts = {
  display: 'Manrope_800ExtraBold', heading: 'Manrope_700Bold', headingSemi: 'Manrope_600SemiBold',
  body: 'SourceSans3_400Regular', bodySemi: 'SourceSans3_600SemiBold', bodyBold: 'SourceSans3_700Bold',
} as const;

export const Spacing = { one: 4, two: 8, three: 16, four: 24, five: 32, six: 48 } as const;
export const Radius = { sm: 10, md: 14, lg: 20, xl: 28, pill: 999 } as const;
export const TouchTarget = 44;
export const MaxContentWidth = 720;
