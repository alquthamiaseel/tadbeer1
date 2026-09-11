import { KeyRound, LayoutDashboard, TriangleAlert } from "lucide-react";
import { redirect } from "next/navigation";
import { cookies } from "next/headers";

import { COOKIE, MAX_AGE_SECONDS, authEnabled, passwordMatches, sessionToken } from "@/lib/session";

export const metadata = { title: "Sign in — AI Project Manager" };

async function signIn(formData: FormData) {
  "use server";

  const password = String(formData.get("password") ?? "");
  if (!passwordMatches(password)) {
    redirect("/login?error=1");
  }
  const jar = await cookies();
  jar.set(COOKIE, sessionToken(), {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: MAX_AGE_SECONDS,
  });
  redirect("/");
}

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ error?: string }>;
}) {
  if (!authEnabled()) redirect("/");
  const { error } = await searchParams;

  return (
    <main className="flex min-h-dvh items-center justify-center px-6">
      <div className="animate-rise w-full max-w-sm">
        <div className="mb-6 flex items-center gap-2.5">
          <span className="flex size-9 items-center justify-center rounded-lg bg-accent-soft text-accent">
            <LayoutDashboard className="size-4.5" strokeWidth={2.25} />
          </span>
          <div>
            <p className="font-semibold tracking-tight">AI Project Manager</p>
            <p className="text-xs text-muted">This dashboard is password protected</p>
          </div>
        </div>

        <form
          action={signIn}
          className="rounded-xl border border-border bg-surface p-6 shadow-token-md"
        >
          <label htmlFor="password" className="mb-1.5 block text-xs font-medium text-muted">
            Dashboard password
          </label>
          <div className="relative">
            <KeyRound className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-2" strokeWidth={2.25} />
            <input
              id="password"
              type="password"
              name="password"
              autoFocus
              required
              className="w-full rounded-lg border border-border bg-surface-2/50 py-2.5 pr-3 pl-9 text-sm outline-none transition-colors focus:border-accent focus:bg-surface"
            />
          </div>

          {error ? (
            <p className="mt-3 flex items-center gap-1.5 text-sm text-failed">
              <TriangleAlert className="size-3.5" strokeWidth={2.25} />
              That password is not right.
            </p>
          ) : null}

          <button
            type="submit"
            className="mt-4 w-full rounded-lg bg-accent px-3 py-2.5 text-sm font-medium text-accent-foreground shadow-token-sm transition-transform hover:-translate-y-0.5 active:translate-y-0"
          >
            Sign in
          </button>
        </form>
      </div>
    </main>
  );
}
