import { notFound } from "next/navigation";

import { api, type AuditRow, type RunDetail } from "@/lib/api";
import { requireSession } from "@/lib/session";
import { RunView } from "@/components/run-view";

export const dynamic = "force-dynamic";

/** Fetch outside the render: a 404 from the API is a missing page, not an error. */
async function load(id: string): Promise<[RunDetail, AuditRow[]] | null> {
  try {
    return await Promise.all([api.getRun(id), api.getAudit(id)]);
  } catch (error) {
    if (error instanceof Error && error.message.startsWith("404")) return null;
    throw error;
  }
}

export default async function RunPage({ params }: { params: Promise<{ id: string }> }) {
  await requireSession();
  const { id } = await params;
  const loaded = await load(id);
  if (!loaded) notFound();
  const [run, audit] = loaded;

  return (
    <main className="mx-auto max-w-5xl px-6 py-12">
      <RunView initial={run} audit={audit} />
    </main>
  );
}
