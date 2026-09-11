"use client";

/**
 * The live view of a single run.
 *
 * Seeded with server-rendered state so the page is complete on first paint,
 * then kept current by a server-sent event stream. Each frame is the whole run,
 * not a delta — a run is small, and a stream of deltas would need reconnection
 * logic to work out what it had missed.
 */

import {
  ChevronDown,
  Clock3,
  Coins,
  ExternalLink,
  Gauge,
  GitFork,
  MessageSquare,
  Rocket,
  ScrollText,
  Table2,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import type { Artifact, AuditRow, RunDetail } from "@/lib/api";
import { ArtifactView } from "@/components/artifacts";
import { StatusBadge } from "@/components/status";
import { Timeline } from "@/components/timeline";

const ARTIFACT_ORDER = ["REQUIREMENTS", "PLAN", "WBS", "DIAGRAM", "PROTOTYPE_FILES", "SUMMARY"];

const ARTIFACT_LABEL: Record<string, string> = {
  REQUIREMENTS: "Requirements",
  PLAN: "Project plan",
  WBS: "Work breakdown structure",
  DIAGRAM: "System design",
  PROTOTYPE_FILES: "Prototype",
  SUMMARY: "Summary",
};

const ARTIFACT_ICON: Record<string, React.ComponentType<React.SVGProps<SVGSVGElement>>> = {
  REQUIREMENTS: ScrollText,
  PLAN: ScrollText,
  WBS: Table2,
  DIAGRAM: GitFork,
  PROTOTYPE_FILES: Rocket,
  SUMMARY: Gauge,
};

/** Latest version of each distinct artifact, in pipeline order. */
function latest(artifacts: Artifact[]): Artifact[] {
  const best = new Map<string, Artifact>();
  for (const artifact of artifacts) {
    const key = `${artifact.kind}:${artifact.name}`;
    const current = best.get(key);
    if (!current || artifact.version > current.version) best.set(key, artifact);
  }
  return [...best.values()].sort(
    (a, b) =>
      ARTIFACT_ORDER.indexOf(a.kind) - ARTIFACT_ORDER.indexOf(b.kind) ||
      a.name.localeCompare(b.name),
  );
}

function Links({ run }: { run: RunDetail }) {
  const links: [string, string, React.ComponentType<React.SVGProps<SVGSVGElement>>][] = [
    ["Asana project", run.asana_project_url ?? "", Table2],
    ["GitHub repository", run.github_repo_url ?? "", GitFork],
    ["Live prototype", run.vercel_url ?? "", Rocket],
  ].filter(([, url]) => Boolean(url)) as [string, string, React.ComponentType<React.SVGProps<SVGSVGElement>>][];

  if (links.length === 0) return null;

  return (
    <div className="mb-8 flex flex-wrap gap-2">
      {links.map(([label, url, Icon]) => (
        <a
          key={label}
          href={url}
          target="_blank"
          rel="noreferrer"
          className="group flex items-center gap-2 rounded-full border border-border bg-surface px-3.5 py-1.5 text-sm shadow-token-sm transition-all hover:-translate-y-0.5 hover:border-border-strong hover:shadow-token-md"
        >
          <Icon className="size-3.5 text-accent" strokeWidth={2.25} />
          {label}
          <ExternalLink className="size-3 text-muted-2 transition-colors group-hover:text-foreground" strokeWidth={2.25} />
        </a>
      ))}
    </div>
  );
}

function Audit({ rows }: { rows: AuditRow[] }) {
  const [open, setOpen] = useState(false);
  if (rows.length === 0) return null;
  const tokens = rows.reduce((total, row) => total + row.input_tokens + row.output_tokens, 0);

  return (
    <section className="mt-12 border-t border-border pt-6">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-2 text-left text-[11px] font-semibold tracking-wider text-muted uppercase transition-colors hover:text-foreground"
      >
        <ChevronDown className={`size-3.5 transition-transform ${open ? "rotate-180" : ""}`} strokeWidth={2.5} />
        Call log · {rows.length} calls · {tokens.toLocaleString()} tokens
      </button>
      {open ? (
        <div className="animate-fade-in mt-3 overflow-x-auto rounded-lg border border-border">
          <table className="w-full min-w-[36rem] border-collapse text-left text-xs">
            <thead>
              <tr className="border-b border-border bg-surface-2/60 text-muted">
                <th className="py-2 pr-3 pl-3.5 font-medium">Target</th>
                <th className="py-2 pr-3 font-medium">Duration</th>
                <th className="py-2 pr-3 font-medium">Tokens</th>
                <th className="py-2 pr-3.5 font-medium">Result</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row, index) => (
                <tr key={row.id} className={index % 2 ? "bg-surface-2/25" : ""}>
                  <td className="py-2 pr-3 pl-3.5 font-mono">{row.target}</td>
                  <td className="mono-nums py-2 pr-3">{(row.duration_ms / 1000).toFixed(1)}s</td>
                  <td className="mono-nums py-2 pr-3">{row.input_tokens + row.output_tokens || "—"}</td>
                  <td className="py-2 pr-3.5">
                    {row.ok ? (
                      <span className="text-complete">ok</span>
                    ) : (
                      <span className="text-failed">{row.error}</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </section>
  );
}

export function RunView({ initial, audit }: { initial: RunDetail; audit: AuditRow[] }) {
  const [run, setRun] = useState(initial);
  const [live, setLive] = useState(false);

  useEffect(() => {
    const source = new EventSource(`/api/stream/${initial.id}`);
    source.onopen = () => setLive(true);
    source.onmessage = (event) => setRun(JSON.parse(event.data) as RunDetail);
    source.addEventListener("end", () => {
      setLive(false);
      source.close();
    });
    // The browser reconnects on error by itself; closing here would stop that.
    source.onerror = () => setLive(false);
    return () => source.close();
  }, [initial.id]);

  const artifacts = useMemo(() => latest(run.artifacts), [run.artifacts]);

  return (
    <>
      <header className="animate-rise mb-9">
        <Link
          href="/"
          className="inline-flex items-center gap-1 text-sm text-muted transition-colors hover:text-foreground"
        >
          ← All runs
        </Link>
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">{run.title}</h1>
          <StatusBadge status={run.status} />
          {live ? (
            <span className="flex items-center gap-1.5 rounded-full border border-border bg-surface px-2.5 py-1 text-[11px] font-medium text-muted">
              <span className="relative flex size-1.5">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-complete opacity-75" />
                <span className="relative inline-flex size-1.5 rounded-full bg-complete" />
              </span>
              live
            </span>
          ) : null}
        </div>
        <p className="mt-1.5 flex items-center gap-1.5 text-xs text-muted">
          <Clock3 className="size-3" strokeWidth={2.25} />
          {new Date(run.created_at).toLocaleString()}
          {run.slack_channel_id ? ` · Slack ${run.slack_channel_id}` : ""}
        </p>
      </header>

      {run.error ? (
        <div className="animate-rise mb-8 rounded-xl border border-failed/25 bg-failed-soft p-4 text-sm">
          <p className="font-medium text-failed">This run stopped.</p>
          <pre className="mt-2 overflow-x-auto rounded-md bg-surface/60 p-2.5 text-xs whitespace-pre-wrap text-failed">
            {run.error}
          </pre>
        </div>
      ) : null}

      {run.status === "AWAITING_APPROVAL" ? (
        <div className="animate-rise mb-8 flex gap-3 rounded-xl border border-waiting/25 bg-waiting-soft p-4 text-sm">
          <MessageSquare className="mt-0.5 size-4 shrink-0 text-waiting" strokeWidth={2.25} />
          <div>
            <p className="font-medium text-waiting">Waiting for a decision in Slack.</p>
            <p className="mt-1 text-muted">
              Approve the plan or request changes in the channel this run started from. The
              conversation is where the decision belongs, so the dashboard does not offer the
              buttons.
            </p>
          </div>
        </div>
      ) : null}

      <Links run={run} />

      <div className="grid gap-10 lg:grid-cols-[minmax(0,340px)_minmax(0,1fr)]">
        <section className="animate-rise lg:sticky lg:top-8 lg:self-start" style={{ animationDelay: "60ms" }}>
          <h2 className="mb-4 flex items-center gap-1.5 text-[11px] font-semibold tracking-wider text-muted uppercase">
            <Coins className="size-3.5" strokeWidth={2.25} />
            Pipeline
          </h2>
          <div className="rounded-xl border border-border bg-surface p-5 shadow-token-sm">
            <Timeline stages={run.stages} />
          </div>
        </section>

        <section className="animate-rise" style={{ animationDelay: "120ms" }}>
          <h2 className="mb-4 text-[11px] font-semibold tracking-wider text-muted uppercase">
            Artifacts
          </h2>
          {artifacts.length === 0 ? (
            <div className="rounded-xl border border-dashed border-border-strong px-6 py-10 text-center text-sm text-muted-2">
              Nothing produced yet.
            </div>
          ) : (
            <div className="flex flex-col gap-3">
              {artifacts.map((artifact) => {
                const Icon = ARTIFACT_ICON[artifact.kind] ?? ScrollText;
                return (
                  <details
                    key={artifact.id}
                    open
                    className="group rounded-xl border border-border bg-surface p-5 shadow-token-sm"
                  >
                    <summary className="flex cursor-pointer list-none items-center gap-2.5 marker:content-none">
                      <span className="flex size-7 shrink-0 items-center justify-center rounded-md bg-accent-soft text-accent">
                        <Icon className="size-3.5" strokeWidth={2.25} />
                      </span>
                      <span className="font-medium">{ARTIFACT_LABEL[artifact.kind] ?? artifact.kind}</span>
                      {artifact.kind === "DIAGRAM" ? (
                        <span className="text-muted">· {artifact.name}</span>
                      ) : null}
                      {artifact.version > 1 ? (
                        <span className="rounded-full bg-accent-soft px-2 py-0.5 text-[10px] font-medium text-accent">
                          revision {artifact.version}
                        </span>
                      ) : null}
                      <ChevronDown className="ml-auto size-4 shrink-0 text-muted-2 transition-transform group-open:rotate-180" strokeWidth={2.25} />
                    </summary>
                    <div className="mt-5 border-t border-border pt-5">
                      <ArtifactView artifact={artifact} />
                    </div>
                  </details>
                );
              })}
            </div>
          )}
        </section>
      </div>

      <Audit rows={audit} />
    </>
  );
}
