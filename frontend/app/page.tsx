import Link from "next/link";
import { ArrowUpRight, GitFork, LayoutDashboard, Rocket, Sparkles } from "lucide-react";

import { api, type RunSummary } from "@/lib/api";
import { requireSession } from "@/lib/session";
import { StatusBadge } from "@/components/status";
import { STAGE_META } from "@/components/timeline";

export const dynamic = "force-dynamic";

async function loadRuns(): Promise<{ runs: RunSummary[]; error: string | null }> {
  try {
    return { runs: await api.listRuns(), error: null };
  } catch (error) {
    return { runs: [], error: error instanceof Error ? error.message : String(error) };
  }
}

function timeAgo(iso: string): string {
  const seconds = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  const units: [number, string][] = [
    [86400, "d"],
    [3600, "h"],
    [60, "m"],
  ];
  for (const [unit, suffix] of units) {
    if (seconds >= unit) return `${Math.floor(seconds / unit)}${suffix} ago`;
  }
  return "just now";
}

export default async function Home() {
  await requireSession();
  const { runs, error } = await loadRuns();

  const counts = {
    complete: runs.filter((r) => r.status === "COMPLETE").length,
    active: runs.filter((r) => r.status === "RUNNING" || r.status === "PENDING").length,
    waiting: runs.filter((r) => r.status === "AWAITING_APPROVAL").length,
  };

  return (
    <main className="mx-auto max-w-5xl px-6 py-14 sm:py-20">
      <header className="animate-rise mb-14">
        <div className="mb-5 inline-flex items-center gap-2 rounded-full border border-border bg-surface px-3 py-1 text-xs font-medium text-muted shadow-token-sm">
          <LayoutDashboard className="size-3.5 text-accent" strokeWidth={2.5} />
          Agentic project manager
        </div>
        <h1 className="text-4xl font-semibold tracking-tight text-balance sm:text-5xl">
          From a Slack conversation
          <br />
          to a deployed prototype.
        </h1>
        <p className="mt-4 max-w-xl text-[15px] leading-relaxed text-muted">
          Six stages, one human decision. Requirements, a plan, a work breakdown in Asana, system
          design in Mermaid, and a live prototype — generated, then reviewed where the
          conversation already happens.
        </p>
      </header>

      <section className="animate-rise mb-14" style={{ animationDelay: "60ms" }}>
        <ol className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          {Object.entries(STAGE_META).map(([kind, meta], index) => {
            const Icon = meta.icon;
            return (
              <li
                key={kind}
                className="group relative flex flex-col gap-2.5 overflow-hidden rounded-lg border border-border bg-surface px-3.5 py-3 shadow-token-sm transition-colors hover:border-border-strong"
              >
                <div className="flex items-center justify-between">
                  <span className="flex size-7 items-center justify-center rounded-md bg-accent-soft text-accent">
                    <Icon className="size-3.5" strokeWidth={2.25} />
                  </span>
                  <span className="text-[11px] tabular-nums text-muted-2">{index + 1}</span>
                </div>
                <span className="text-[13px] font-medium">{meta.label}</span>
                {index < 5 ? (
                  <span
                    aria-hidden
                    className="absolute top-1/2 -right-1.5 hidden h-px w-3 -translate-y-1/2 bg-border-strong lg:block"
                  />
                ) : null}
              </li>
            );
          })}
        </ol>
      </section>

      <section className="animate-rise" style={{ animationDelay: "120ms" }}>
        <div className="mb-4 flex flex-wrap items-baseline justify-between gap-3">
          <h2 className="text-xs font-semibold tracking-wider text-muted uppercase">Runs</h2>
          {runs.length > 0 ? (
            <div className="flex items-center gap-4 text-xs text-muted">
              {counts.waiting > 0 ? (
                <span className="flex items-center gap-1.5 font-medium text-waiting">
                  <span className="size-1.5 rounded-full bg-waiting" />
                  {counts.waiting} awaiting approval
                </span>
              ) : null}
              {counts.active > 0 ? (
                <span className="flex items-center gap-1.5">
                  <span className="size-1.5 animate-pulse rounded-full bg-running" />
                  {counts.active} running
                </span>
              ) : null}
              <span>{counts.complete} complete</span>
            </div>
          ) : null}
        </div>

        {error ? (
          <div className="rounded-xl border border-failed/25 bg-failed-soft px-5 py-4 text-sm">
            <p className="font-medium text-failed">Cannot reach the backend.</p>
            <p className="mt-1 text-muted">{error}</p>
            <p className="mt-3 text-muted">
              Start it with <code className="rounded bg-surface px-1.5 py-0.5 font-mono text-[13px]">make api</code>.
            </p>
          </div>
        ) : runs.length === 0 ? (
          <div className="rounded-xl border border-dashed border-border-strong bg-surface/50 px-8 py-14 text-center">
            <div className="mx-auto mb-4 flex size-11 items-center justify-center rounded-full bg-accent-soft text-accent">
              <Sparkles className="size-5" strokeWidth={2} />
            </div>
            <p className="text-sm font-medium">No runs yet</p>
            <p className="mx-auto mt-1.5 max-w-xs text-sm text-muted">
              Discuss what you want built in a channel the bot has joined, then run{" "}
              <code className="rounded bg-surface-2 px-1.5 py-0.5 font-mono text-[13px]">/pm start</code>.
            </p>
          </div>
        ) : (
          <ul className="flex flex-col gap-2.5">
            {runs.map((run, index) => {
              const meta = run.current_stage ? STAGE_META[run.current_stage] : null;
              const StageIcon = meta?.icon;
              return (
                <li
                  key={run.id}
                  className="animate-rise"
                  style={{ animationDelay: `${160 + index * 40}ms` }}
                >
                  <Link
                    href={`/runs/${run.id}`}
                    className="group flex items-center gap-4 rounded-xl border border-border bg-surface px-5 py-4 shadow-token-sm transition-all hover:-translate-y-0.5 hover:border-border-strong hover:shadow-token-md"
                  >
                    <div className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-surface-2 text-muted transition-colors group-hover:bg-accent-soft group-hover:text-accent">
                      {StageIcon ? <StageIcon className="size-4.5" strokeWidth={2} /> : <Sparkles className="size-4.5" strokeWidth={2} />}
                    </div>

                    <div className="min-w-0 flex-1">
                      <p className="truncate font-medium">{run.title}</p>
                      <p className="mt-0.5 flex flex-wrap items-center gap-x-2 text-xs text-muted">
                        <span>{timeAgo(run.created_at)}</span>
                        {run.current_stage ? (
                          <>
                            <span className="text-muted-2">·</span>
                            <span>{meta?.label ?? run.current_stage}</span>
                          </>
                        ) : null}
                        {run.vercel_url ? (
                          <>
                            <span className="text-muted-2">·</span>
                            <span className="inline-flex items-center gap-1 text-complete">
                              <Rocket className="size-3" strokeWidth={2.5} />
                              deployed
                            </span>
                          </>
                        ) : null}
                        {run.github_repo_url ? (
                          <>
                            <span className="text-muted-2">·</span>
                            <span className="inline-flex items-center gap-1">
                              <GitFork className="size-3" strokeWidth={2.5} />
                              committed
                            </span>
                          </>
                        ) : null}
                      </p>
                    </div>

                    <StatusBadge status={run.status} />
                    <ArrowUpRight className="size-4 shrink-0 text-muted-2 opacity-0 transition-all group-hover:translate-x-0.5 group-hover:-translate-y-0.5 group-hover:text-foreground group-hover:opacity-100" />
                  </Link>
                </li>
              );
            })}
          </ul>
        )}
      </section>
    </main>
  );
}
