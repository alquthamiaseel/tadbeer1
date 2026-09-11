import {
  CheckCircle2,
  CircleDashed,
  Loader2,
  MinusCircle,
  OctagonX,
  TimerReset,
} from "lucide-react";

import type { RunStatus, StageKind, StageStatus } from "@/lib/api";

export const STAGES: StageKind[] = ["INGEST", "PLAN", "WBS", "DESIGN", "PROTOTYPE", "DONE"];

type Status = RunStatus | StageStatus;

const TONE: Record<Status, string> = {
  PENDING: "bg-surface-2 text-muted",
  RUNNING: "bg-running-soft text-running",
  AWAITING_APPROVAL: "bg-waiting-soft text-waiting",
  COMPLETE: "bg-complete-soft text-complete",
  FAILED: "bg-failed-soft text-failed",
  SKIPPED: "bg-surface-2 text-muted-2",
  CANCELLED: "bg-surface-2 text-muted-2",
};

const DOT: Record<Status, string> = {
  PENDING: "bg-muted-2",
  RUNNING: "bg-running",
  AWAITING_APPROVAL: "bg-waiting",
  COMPLETE: "bg-complete",
  FAILED: "bg-failed",
  SKIPPED: "bg-muted-2",
  CANCELLED: "bg-muted-2",
};

const ICON: Record<Status, React.ComponentType<React.SVGProps<SVGSVGElement>>> = {
  PENDING: CircleDashed,
  RUNNING: Loader2,
  AWAITING_APPROVAL: TimerReset,
  COMPLETE: CheckCircle2,
  FAILED: OctagonX,
  SKIPPED: MinusCircle,
  CANCELLED: MinusCircle,
};

const LABEL: Record<Status, string> = {
  PENDING: "Pending",
  RUNNING: "Running",
  AWAITING_APPROVAL: "Awaiting approval",
  COMPLETE: "Complete",
  FAILED: "Failed",
  SKIPPED: "Skipped",
  CANCELLED: "Cancelled",
};

export function StatusBadge({ status }: { status: Status }) {
  const Icon = ICON[status];
  return (
    <span
      className={`inline-flex shrink-0 items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${TONE[status]}`}
    >
      <Icon className={`size-3.5 ${status === "RUNNING" ? "animate-spin" : ""}`} strokeWidth={2.5} />
      {LABEL[status]}
    </span>
  );
}

/** A bare status dot, for places a full badge would be too heavy — table rows, timelines. */
export function StatusDot({ status }: { status: Status }) {
  return (
    <span className="relative flex size-2.5 shrink-0">
      {status === "RUNNING" ? (
        <span className={`absolute inline-flex h-full w-full animate-ping rounded-full ${DOT[status]} opacity-60`} />
      ) : null}
      <span className={`relative inline-flex size-2.5 rounded-full ${DOT[status]}`} />
    </span>
  );
}
