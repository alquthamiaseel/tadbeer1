/**
 * Dashboard sign-in.
 *
 * One shared password, held by the Next.js server and never sent to the
 * browser. A correct password sets an httpOnly cookie holding an HMAC of the
 * password rather than the password itself, so a stolen cookie cannot be
 * replayed against the backend API.
 *
 * Sign-in is skipped entirely when DASHBOARD_AUTH is not "true", which is the
 * normal case: on a laptop the dashboard is only reachable from the laptop.
 */

import { createHmac, timingSafeEqual } from "node:crypto";

export const COOKIE = "pm_session";
export const MAX_AGE_SECONDS = 60 * 60 * 12;

const PASSWORD = process.env.DASHBOARD_PASSWORD ?? "";

export function authEnabled(): boolean {
  return process.env.DASHBOARD_AUTH === "true";
}

/** The cookie value for a valid session: proof of the password, not the password. */
export function sessionToken(): string {
  return createHmac("sha256", PASSWORD).update("pm-fyp-dashboard").digest("hex");
}

export function passwordMatches(candidate: string): boolean {
  const a = Buffer.from(candidate);
  const b = Buffer.from(PASSWORD);
  return a.length === b.length && timingSafeEqual(a, b);
}

export function tokenMatches(candidate: string | undefined): boolean {
  if (!candidate) return false;
  const a = Buffer.from(candidate);
  const b = Buffer.from(sessionToken());
  return a.length === b.length && timingSafeEqual(a, b);
}

/** Redirect to the sign-in page unless this request carries a valid session. */
export async function requireSession(): Promise<void> {
  if (!authEnabled()) return;
  const { cookies } = await import("next/headers");
  const { redirect } = await import("next/navigation");
  const jar = await cookies();
  if (!tokenMatches(jar.get(COOKIE)?.value)) {
    redirect("/login");
  }
}
