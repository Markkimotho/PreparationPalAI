import { apiFetch } from './access';
let sent = 0;
export function installDiagnostics() {
  const report = (kind: string) => {
    if (sent++ >= 5) return;
    // Never transmit messages, stacks, URLs, prompts or document content.
    apiFetch('/api/diagnostics/frontend', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ kind }),
    }).catch(() => {});
  };
  window.addEventListener('error', () => report('script'));
  window.addEventListener('unhandledrejection', () => report('unhandled-rejection'));
}
