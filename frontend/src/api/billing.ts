/** Turn the server's 402 "not enough credits" body into one clear, actionable sentence. */
export interface CreditsBody {
  detail?: string;
  balance_credits?: number;
  required_credits?: number;
  top_up_url?: string;
}

export function creditsMessage(body: CreditsBody): string {
  const parts = [body.detail ?? "Not enough credits for this action."];
  if (typeof body.balance_credits === "number" && typeof body.required_credits === "number") {
    parts.push(`You have ${body.balance_credits} credits and this needs about ${body.required_credits}.`);
  }
  if (body.top_up_url) parts.push(`Top up: ${body.top_up_url}`);
  return parts.join(" ");
}
