import type { InputType } from "./types";

export interface Scenario {
  id: string;
  name: string;
  type: InputType;
  content: string;
}

export const scenarios: Scenario[] = [
  {
    id: "github-phish",
    name: "GitHub credential lure",
    type: "message",
    content: "URGENT: Your GitHub account has been compromised. Verify immediately at [https://github-security-check.zip](https://github-security-check.zip) and enter your password and verification code.",
  },
  {
    id: "executive-impersonation",
    name: "Executive impersonation",
    type: "email",
    content: "From: ceo-office@example.test\nSubject: Confidential wire transfer\n\nI am in a meeting. Keep this private and wire $8,400 to the updated vendor account before 3 PM.",
  },
  {
    id: "banking-scam",
    name: "Bank account suspension",
    type: "message",
    content: "FINAL NOTICE: Your bank account will be suspended today. Sign in at https://secure-bank-verify.click and confirm your password and one-time code.",
  },
  {
    id: "ai-impersonation",
    name: "AI voice impersonation follow-up",
    type: "email",
    content: "I know the call sounded like Jordan, but verify the unexpected payment request through the company directory before acting. Never rely on voice alone.",
  },
  {
    id: "legitimate-security",
    name: "Routine security notice",
    type: "email",
    content: "Your security settings were updated. If you made this change, no action is needed. To review recent activity, open the official site manually and visit its security settings.",
  },
];