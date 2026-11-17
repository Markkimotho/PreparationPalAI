import { Redirect } from 'expo-router';

/** The sign-in browser returns here; the session already has the tokens, so go home. */
export default function AuthCallback() {
  return <Redirect href="/" />;
}
