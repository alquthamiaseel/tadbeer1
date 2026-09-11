import {
  CheckCircle2,
  Clock3,
  Coins,
  Compass,
  FileSearch,
  ClipboardList,
  Loader2,
  OctagonX,
  RefreshCw,
  Rocket,
  Sparkles,
  TimerReset,
  Workflow,
} from "lucide-react";

import type { Stage, StageKind } from "@/lib/api";
import { StatusBadge } from "@/components/status";

const STAGE_META: Record<StageKind, { label: string; description: string; icon: React.ComponentType<React.SVGProps<SVGSVGElement>> }> = {
  INGEST: {
    label: "Ingest",
    description: "Read the Slack conversation and extract structured requirements",
    icon: FileSearch,
  },
  PLAN: {
    label: "Plan",
    description: "Draft a delivery plan and wait for a human decision in Slack",
    icon: ClipboardList,
  },
  WBS: {
    label: "Breakdown",
    description: "Build a dependency-aware task graph and publish it to Asana",
    icon: Workflow,
  },
  DESIGN: {
    label: "Design",
    description: "Produce use-case, architecture, ER and sequence diagrams",
    icon: Compass,
  },
  PROTOTYPE: {
    label: "Prototype",
    description: "Generate a clickable prototype, commit it, and deploy it",
    icon: Rocket,
  },
  DONE: {
    label: "Done",
    description: "Summarise everything the run produced",
    icon: Sparkles,
  },
};

function duration(seconds: number | null): string {
  if (seconds === null) return "";
  if (seconds < 60) return `${seconds.toFixed(1)}s`;
  return `${Math.floor(seconds / 60)}m ${Math.round(seconds % 60)}s`;
}

const RING: Record<Stage["status"], string> = {
  PENDING: "border-border bg-surface text-muted-2",
  RUNNING: "border-running bg-running-soft text-running",
  AWAITING_APPROVAL: "border-waiting bg-waiting-soft text-waiting",
  COMPLETE: "border-complete bg-complete-soft text-complete",
  FAILED: "border-failed bg-failed-soft text-failed",
  SKIPPED: "border-border bg-surface text-muted-2",
};

function NodeIcon({ stage }: { stage: Stage }) {
  if (stage.status === "RUNNING") return <Loader2 className="size-4 animate-spin" strokeWidth={2.5} />;
  if (stage.status === "COMPLETE") return <CheckCircle2 className="size-4" strokeWidth={2.5} />;
  if (stage.status === "FAILED") return <OctagonX className="size-4" strokeWidth={2.5} />;
  if (stage.status === "AWAITING_APPROVAL") return <TimerReset className="size-4" strokeWidth={2.5} />;
  const Icon = STAGE_META[stage.kind].icon;
  return <Icon className="size-4" strokeWidth={2} />;
}

export function Timeline({ stages }: { stages: Stage[] }) {
  return (
    <ol className="flex flex-col">
      {stages.map((stage, index) => {
        const meta = STAGE_META[stage.kind];
        const isLast = index === stages.length - 1;
        const spent = stage.input_tokens + stage.output_tokens;

        return (
          <li key={stage.id} className="relative flex gap-4 pb-7 last:pb-0">
            {!isLast ? (
              <span
                aria-hidden
                className={`absolute top-9 left-[15px] w-px ${
                  stage.status === "COMPLETE" ? "bg-complete/40" : "bg-border"
                }`}
                style={{ height: "calc(100% - 1.25rem)" }}
              />
            ) : null}

            <span
              className={`relative z-10 flex size-8 shrink-0 items-center justify-center rounded-full border-2 ${RING[stage.status]}`}
            >
              <NodeIcon stage={stage} />
            </span>

            <div className="min-w-0 flex-1 pt-0.5">
              <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
                <h3 className="font-medium">{meta.label}</h3>
                <StatusBadge status={stage.status} />
                <span className="flex items-center gap-3 text-xs text-muted-2 mono-nums">
                  {stage.duration_seconds !== null ? (
                    <span className="flex items-center gap-1">
                      <Clock3 className="size-3" strokeWidth={2.25} />
                      {duration(stage.duration_seconds)}
                    </span>
                  ) : null}
                  {spent > 0 ? (
                    <span className="flex items-center gap-1">
                      <Coins className="size-3" strokeWidth={2.25} />
                      {spent.toLocaleString()}
                    </span>
                  ) : null}
                  {stage.attempt > 1 ? (
                    <span className="flex items-center gap-1">
                      <RefreshCw className="size-3" strokeWidth={2.25} />
                      attempt {stage.attempt}
                    </span>
                  ) : null}
                </span>
              </div>
              <p className="mt-0.5 text-sm text-muted">{meta.description}</p>
              {stage.error ? (
                <pre className="mt-2.5 overflow-x-auto rounded-lg border border-failed/25 bg-failed-soft px-3.5 py-3 text-xs whitespace-pre-wrap text-failed">
                  {stage.error}
                </pre>
              ) : null}
            </div>
          </li>
        );
      })}
    </ol>
  );
}

export { STAGE_META };
