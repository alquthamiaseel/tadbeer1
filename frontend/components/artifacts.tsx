/**
 * Artifact viewers.
 *
 * Each pipeline stage produces a differently-shaped artifact, and the point of
 * the dashboard is that you can read them — a JSON dump would make the run
 * inspectable without making it legible. Every viewer falls back to raw JSON if
 * the shape is not what it expects, so a schema change degrades to ugly rather
 * than to a blank page.
 */

import {
  CircleHelp,
  ExternalLink,
  Gauge,
  ListChecks,
  Milestone,
  ShieldAlert,
  Sparkles,
  TriangleAlert,
} from "lucide-react";

import type { Artifact } from "@/lib/api";
import { Mermaid } from "@/components/mermaid";

/**
 * The shape of each artifact's `data`, mirroring the Pydantic models in
 * backend/app/schemas/. Every field is optional: these objects come off the
 * wire as JSON, and a viewer that assumes a field is present renders a blank
 * page when a schema changes instead of degrading gracefully.
 */

interface RequirementsData {
  goal?: string;
  actors?: { name?: string; description?: string }[];
  features?: {
    title?: string;
    description?: string;
    priority?: string;
    source?: string;
  }[];
  constraints?: { kind?: string; description?: string }[];
  assumptions?: string[];
  open_questions?: string[];
  non_functional?: string[];
  out_of_scope?: string[];
}

interface PlanData {
  executive_summary?: string;
  estimated_total_days?: number;
  phases?: {
    name?: string;
    objective?: string;
    deliverables?: string[];
    estimated_duration_days?: number;
  }[];
  milestones?: { name?: string; success_criteria?: string; target_phase?: string }[];
  risks?: { title?: string; likelihood?: string; impact?: string; mitigation?: string }[];
  in_scope?: string[];
  out_of_scope?: string[];
  assumptions?: string[];
  open_questions?: string[];
}

interface WbsData {
  project_summary?: string;
  tasks?: {
    id: string;
    name?: string;
    description?: string;
    phase?: string;
    owner_role?: string;
    estimate_days?: number;
    depends_on?: string[];
    constraints?: string[];
  }[];
}

interface PrototypeData {
  live_url?: string;
  screens?: { name?: string; purpose?: string }[];
  notes?: string[];
}

interface SummaryData {
  counts?: Record<string, number>;
  tokens?: { input?: number; output?: number };
  open_questions?: string[];
}

function Section({
  title,
  icon: Icon,
  children,
}: {
  title: string;
  icon?: React.ComponentType<React.SVGProps<SVGSVGElement>>;
  children: React.ReactNode;
}) {
  return (
    <section className="mb-7 last:mb-0">
      <h4 className="mb-2.5 flex items-center gap-1.5 text-[11px] font-semibold tracking-wider text-muted uppercase">
        {Icon ? <Icon className="size-3.5" strokeWidth={2.25} /> : null}
        {title}
      </h4>
      {children}
    </section>
  );
}

function Bullets({ items }: { items: unknown }) {
  const list = Array.isArray(items) ? items.map(String).filter(Boolean) : [];
  if (list.length === 0) return <p className="text-sm text-muted-2 italic">None recorded.</p>;
  return (
    <ul className="space-y-1.5 text-sm">
      {list.map((item, index) => (
        <li key={index} className="flex gap-2">
          <span className="mt-2 size-1 shrink-0 rounded-full bg-muted-2" />
          <span className="text-foreground/90">{item}</span>
        </li>
      ))}
    </ul>
  );
}

function Raw({ value }: { value: unknown }) {
  return (
    <pre className="overflow-x-auto rounded-lg bg-surface-2 p-3.5 text-xs">
      {JSON.stringify(value, null, 2)}
    </pre>
  );
}

const PRIORITY_TONE: Record<string, string> = {
  MUST: "bg-failed-soft text-failed",
  SHOULD: "bg-waiting-soft text-waiting",
  COULD: "bg-surface-2 text-muted",
  WONT: "bg-surface-2 text-muted-2 line-through",
};

const RISK_TONE: Record<string, string> = {
  high: "text-failed",
  medium: "text-waiting",
  low: "text-complete",
};

function Requirements({ data }: { data: RequirementsData }) {
  return (
    <>
      <Section title="Goal" icon={Sparkles}>
        <p className="text-[15px] leading-relaxed">{data.goal}</p>
      </Section>

      <Section title="Actors">
        <div className="flex flex-wrap gap-2">
          {(data.actors ?? []).map((actor, index) => (
            <div
              key={index}
              className="rounded-lg border border-border bg-surface-2/60 px-3 py-2 text-sm"
            >
              <span className="font-medium">{actor.name}</span>
              <span className="text-muted"> — {actor.description}</span>
            </div>
          ))}
        </div>
      </Section>

      <Section title={`Features · ${(data.features ?? []).length}`} icon={ListChecks}>
        <ul className="space-y-2">
          {(data.features ?? []).map((feature, index) => (
            <li
              key={index}
              className="rounded-lg border border-border bg-surface-2/40 px-3.5 py-2.5"
            >
              <div className="flex flex-wrap items-baseline gap-2">
                <span
                  className={`rounded px-1.5 py-0.5 text-[10px] font-semibold tracking-wide ${
                    PRIORITY_TONE[feature.priority ?? ""] ?? PRIORITY_TONE.COULD
                  }`}
                >
                  {feature.priority}
                </span>
                <span className="text-sm font-medium">{feature.title}</span>
              </div>
              <p className="mt-1 text-sm text-muted">{feature.description}</p>
              {feature.source ? (
                <p className="mt-1.5 text-xs text-muted-2 italic">from: {feature.source}</p>
              ) : null}
            </li>
          ))}
        </ul>
      </Section>

      <Section title="Constraints" icon={ShieldAlert}>
        <ul className="space-y-1.5 text-sm">
          {(data.constraints ?? []).map((constraint, index) => (
            <li key={index} className="flex gap-2">
              <span className="shrink-0 rounded bg-surface-2 px-1.5 py-0.5 text-[10px] font-medium tracking-wide text-muted uppercase">
                {constraint.kind}
              </span>
              <span>{constraint.description}</span>
            </li>
          ))}
        </ul>
      </Section>

      <div className="grid gap-6 sm:grid-cols-2">
        <Section title="Assumptions">
          <Bullets items={data.assumptions} />
        </Section>
        <Section title="Open questions" icon={CircleHelp}>
          <Bullets items={data.open_questions} />
        </Section>
        <Section title="Non-functional">
          <Bullets items={data.non_functional} />
        </Section>
        <Section title="Out of scope">
          <Bullets items={data.out_of_scope} />
        </Section>
      </div>
    </>
  );
}

function Plan({ data }: { data: PlanData }) {
  return (
    <>
      <Section title="Executive summary" icon={Sparkles}>
        <p className="text-[15px] leading-relaxed">{data.executive_summary}</p>
      </Section>

      <Section title={`Phases · ${data.estimated_total_days ?? "?"} working days total`} icon={Milestone}>
        <ol className="relative flex flex-col gap-3 border-l border-border pl-5">
          {(data.phases ?? []).map((phase, index) => (
            <li key={index} className="relative">
              <span className="absolute top-1.5 -left-[23px] size-2.5 rounded-full border-2 border-surface bg-accent" />
              <div className="rounded-lg border border-border bg-surface-2/40 p-3.5">
                <div className="flex items-baseline justify-between gap-3">
                  <span className="font-medium">{phase.name}</span>
                  <span className="mono-nums shrink-0 text-xs text-muted">
                    {phase.estimated_duration_days} days
                  </span>
                </div>
                <p className="mt-1 text-sm text-muted">{phase.objective}</p>
                <Bullets items={phase.deliverables} />
              </div>
            </li>
          ))}
        </ol>
      </Section>

      <Section title="Milestones" icon={Milestone}>
        <ul className="space-y-1.5 text-sm">
          {(data.milestones ?? []).map((milestone, index) => (
            <li key={index}>
              <span className="font-medium">{milestone.name}</span>
              <span className="text-muted">
                {" "}
                — {milestone.success_criteria} ({milestone.target_phase})
              </span>
            </li>
          ))}
        </ul>
      </Section>

      <Section title="Risks" icon={TriangleAlert}>
        <ul className="space-y-2">
          {(data.risks ?? []).map((risk, index) => (
            <li key={index} className="flex items-start gap-2.5 text-sm">
              <span
                className={`mt-1.5 size-1.5 shrink-0 rounded-full ${
                  risk.likelihood === "high" || risk.impact === "high"
                    ? "bg-failed"
                    : risk.likelihood === "medium" || risk.impact === "medium"
                      ? "bg-waiting"
                      : "bg-complete"
                }`}
              />
              <p>
                <span className="font-medium">{risk.title}</span>
                <span
                  className={`ml-1.5 text-xs ${RISK_TONE[risk.likelihood ?? ""] ?? "text-muted"}`}
                >
                  {risk.likelihood}/{risk.impact}
                </span>
                <span className="text-muted"> — {risk.mitigation}</span>
              </p>
            </li>
          ))}
        </ul>
      </Section>

      <div className="grid gap-6 sm:grid-cols-2">
        <Section title="In scope">
          <Bullets items={data.in_scope} />
        </Section>
        <Section title="Out of scope">
          <Bullets items={data.out_of_scope} />
        </Section>
        <Section title="Assumptions">
          <Bullets items={data.assumptions} />
        </Section>
        <Section title="Open questions" icon={CircleHelp}>
          <Bullets items={data.open_questions} />
        </Section>
      </div>
    </>
  );
}

function Wbs({ data }: { data: WbsData }) {
  const tasks = data.tasks ?? [];
  const names = new Map(tasks.map((task) => [task.id, task.name ?? task.id]));

  return (
    <>
      <Section title="Approach" icon={Sparkles}>
        <p className="text-[15px] leading-relaxed">{data.project_summary}</p>
      </Section>

      <Section title={`Tasks · ${tasks.length}`} icon={ListChecks}>
        <div className="overflow-x-auto rounded-lg border border-border">
          <table className="w-full min-w-[46rem] border-collapse text-left text-sm">
            <thead>
              <tr className="border-b border-border bg-surface-2/60 text-[11px] font-semibold tracking-wider text-muted uppercase">
                <th className="py-2.5 pr-3 pl-3.5 font-semibold">Task</th>
                <th className="py-2.5 pr-3 font-semibold">Phase</th>
                <th className="py-2.5 pr-3 font-semibold">Owner</th>
                <th className="py-2.5 pr-3 font-semibold">Days</th>
                <th className="py-2.5 pr-3.5 font-semibold">Depends on</th>
              </tr>
            </thead>
            <tbody>
              {tasks.map((task, index) => (
                <tr
                  key={task.id}
                  className={index % 2 ? "bg-surface-2/25" : ""}
                >
                  <td className="py-2.5 pr-3 pl-3.5 align-top">
                    <div className="font-medium">{task.name}</div>
                    <div className="mt-0.5 text-xs text-muted">{task.description}</div>
                    {(task.constraints?.length ?? 0) > 0 ? (
                      <div className="mt-1.5 flex flex-wrap gap-1">
                        {task.constraints!.map((c, i) => (
                          <span
                            key={i}
                            className="rounded bg-waiting-soft px-1.5 py-0.5 text-[10px] font-medium text-waiting"
                          >
                            {c}
                          </span>
                        ))}
                      </div>
                    ) : null}
                  </td>
                  <td className="py-2.5 pr-3 align-top text-muted">{task.phase}</td>
                  <td className="py-2.5 pr-3 align-top text-muted">{task.owner_role}</td>
                  <td className="mono-nums py-2.5 pr-3 align-top">{task.estimate_days}</td>
                  <td className="py-2.5 pr-3.5 align-top text-muted">
                    {(task.depends_on ?? []).map((id) => names.get(id) ?? id).join(", ") || "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>
    </>
  );
}

function DiagramView({ artifact }: { artifact: Artifact }) {
  const explanation = (artifact.data?.explanation ?? "") as string;
  return (
    <>
      {explanation ? <p className="mb-4 text-sm text-muted">{explanation}</p> : null}
      {artifact.text ? (
        <Mermaid source={artifact.text} id={artifact.id} />
      ) : (
        <p className="text-sm text-muted-2">This diagram has no source.</p>
      )}
      <details className="mt-3">
        <summary className="cursor-pointer text-xs text-muted-2 hover:text-muted">
          Mermaid source
        </summary>
        <pre className="mt-2 overflow-x-auto rounded-lg bg-surface-2 p-3.5 text-xs">
          {artifact.text}
        </pre>
      </details>
    </>
  );
}

function PrototypeView({ data }: { data: PrototypeData }) {
  const live = data.live_url;
  return (
    <>
      <Section title="Screens" icon={ListChecks}>
        <ul className="space-y-1.5 text-sm">
          {(data.screens ?? []).map((screen, index) => (
            <li key={index}>
              <span className="font-medium">{screen.name}</span>
              <span className="text-muted"> — {screen.purpose}</span>
            </li>
          ))}
        </ul>
      </Section>

      <Section title="What it fakes" icon={TriangleAlert}>
        <Bullets items={data.notes} />
      </Section>

      {live ? (
        <Section title="Live prototype">
          <div className="overflow-hidden rounded-lg border border-border shadow-token-sm">
            <div className="flex items-center gap-1.5 border-b border-border bg-surface-2 px-3 py-2">
              <span className="size-2.5 rounded-full bg-failed/50" />
              <span className="size-2.5 rounded-full bg-waiting/50" />
              <span className="size-2.5 rounded-full bg-complete/50" />
              <span className="mono-nums ml-2 truncate text-xs text-muted">{live}</span>
            </div>
            <iframe
              src={live}
              title="Generated prototype"
              className="h-[32rem] w-full bg-white"
              sandbox="allow-scripts allow-same-origin allow-popups"
            />
          </div>
          <a
            href={live}
            target="_blank"
            rel="noreferrer"
            className="mt-2.5 inline-flex items-center gap-1.5 text-sm text-accent underline-offset-4 hover:underline"
          >
            Open in a new tab
            <ExternalLink className="size-3.5" strokeWidth={2.25} />
          </a>
        </Section>
      ) : null}
    </>
  );
}

function SummaryView({ data }: { data: SummaryData }) {
  const counts = data.counts ?? {};
  const tokens = data.tokens ?? {};
  return (
    <>
      <Section title="Produced" icon={Sparkles}>
        <dl className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          {Object.entries(counts).map(([label, value]) => (
            <div
              key={label}
              className="rounded-lg border border-border bg-surface-2/40 p-3.5 text-center"
            >
              <dd className="mono-nums text-2xl font-semibold text-accent">{value}</dd>
              <dt className="mt-0.5 text-[11px] tracking-wide text-muted uppercase">{label}</dt>
            </div>
          ))}
        </dl>
      </Section>
      <Section title="Model usage" icon={Gauge}>
        <p className="mono-nums text-sm text-muted">
          {(tokens.input ?? 0).toLocaleString()} input tokens ·{" "}
          {(tokens.output ?? 0).toLocaleString()} output tokens
        </p>
      </Section>
      {(data.open_questions ?? []).length > 0 ? (
        <Section title="Still open" icon={CircleHelp}>
          <Bullets items={data.open_questions} />
        </Section>
      ) : null}
    </>
  );
}

export function ArtifactView({ artifact }: { artifact: Artifact }) {
  // One unchecked boundary, here, where JSON becomes typed. Each viewer below
  // then works against a declared shape rather than an index signature.
  const data = artifact.data ?? {};

  switch (artifact.kind) {
    case "REQUIREMENTS":
      return <Requirements data={data as RequirementsData} />;
    case "PLAN":
      return <Plan data={data as PlanData} />;
    case "WBS":
      return <Wbs data={data as WbsData} />;
    case "DIAGRAM":
      return <DiagramView artifact={artifact} />;
    case "PROTOTYPE_FILES":
      return <PrototypeView data={data as PrototypeData} />;
    case "SUMMARY":
      return <SummaryView data={data as SummaryData} />;
    default:
      return <Raw value={artifact.data ?? artifact.text} />;
  }
}
