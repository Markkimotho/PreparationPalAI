/** Where the app talks to. Set EXPO_PUBLIC_API_URL per build profile (eas.json); nothing secret lives here. */
export const API_URL = (process.env.EXPO_PUBLIC_API_URL ?? 'http://localhost:8000').replace(/\/$/, '');
export const APP_SCHEME = 'preparationpal';
