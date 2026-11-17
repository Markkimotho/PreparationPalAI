import { useState } from 'react';

import { Body, Button, Heading, Notice, Screen } from '@/components/ui';
import { useSession } from '@/hooks/use-session';

export function SignIn() {
  const { signIn, notice, error } = useSession();
  const [busy, setBusy] = useState(false);
  return <Screen>
    <Heading>PreparationPalAI</Heading>
    <Body>Study deeply. Prepare confidently. Practise exams, interviews and recaps from your own notes.</Body>
    <Notice text={notice} />
    <Button label="Sign in or create an account" busy={busy} onPress={async () => { setBusy(true); await signIn(); setBusy(false); }} />
    <Body muted>New accounts get 500 free credits after confirming their email.</Body>
    <Notice text={error} kind="error" />
  </Screen>;
}
