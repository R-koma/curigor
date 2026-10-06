import "server-only";

import { Resend } from "resend";

export interface EmailMessage {
  to: string;
  subject: string;
  text: string;
  html: string;
}

let client: Resend | undefined;

export async function sendEmail(message: EmailMessage): Promise<void> {
  const apiKey = process.env.RESEND_API_KEY;
  const from = process.env.EMAIL_FROM;
  if (!apiKey) throw new Error("RESEND_API_KEY is required to send email");
  if (!from) throw new Error("EMAIL_FROM is required to send email");

  client ??= new Resend(apiKey);
  const { error } = await client.emails.send({ from, ...message });
  if (error) {
    console.error(`[email] send failed: ${error.name}`);
    throw new Error(`Email send failed: ${error.name}`);
  }
}
