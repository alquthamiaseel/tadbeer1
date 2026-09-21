export const RUN_STATUS = {
  PENDING: { label: 'Pending', badge: 'bg-slate-100 text-slate-600' },
  RUNNING: { label: 'Running', badge: 'bg-blue-50 text-blue-600' },
  AWAITING_APPROVAL: { label: 'Awaiting approval', badge: 'bg-amber-50 text-amber-600' },
  COMPLETE: { label: 'Complete', badge: 'bg-green-50 text-green-600' },
  FAILED: { label: 'Failed', badge: 'bg-red-50 text-red-600' },
  CANCELLED: { label: 'Cancelled', badge: 'bg-slate-100 text-slate-500' },
}

export const STAGE_LABEL = {
  INGEST: 'Requirements',
  PLAN: 'Planning',
}

export const IN_PROGRESS = new Set(['PENDING', 'RUNNING'])

export function statusInfo(status) {
  return RUN_STATUS[status] || { label: status, badge: 'bg-slate-100 text-slate-600' }
}

export function latestArtifact(run, kind) {
  const matching = (run?.artifacts || []).filter((artifact) => artifact.kind === kind)
  if (matching.length === 0) return null
  return matching.reduce((best, artifact) => (artifact.version > best.version ? artifact : best))
}

export function formatDateTime(iso) {
  return new Date(iso).toLocaleString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}
