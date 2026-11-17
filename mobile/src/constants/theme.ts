/** Brand colours (same mark as the web app) for light and dark mode. */
export const Colors = {
  light: {
    text: '#13221b', textSecondary: '#55625b', background: '#ffffff', backgroundElement: '#f2f6f1',
    backgroundSelected: '#e1ece0', tint: '#194f3c', onTint: '#ffffff', border: '#d6ded7', danger: '#b42318', success: '#16794c',
  },
  dark: {
    text: '#eef4ef', textSecondary: '#a8b4ad', background: '#0d1411', backgroundElement: '#17211c',
    backgroundSelected: '#22302a', tint: '#c9e6bc', onTint: '#0d1411', border: '#2c3a33', danger: '#f97066', success: '#6ccf9b',
  },
} as const;

export type Palette = (typeof Colors)['light'];

export const Spacing = { one: 4, two: 8, three: 16, four: 24, five: 32 } as const;
export const TouchTarget = 44;
export const MaxContentWidth = 720;
