import { Link } from 'react-router-dom'
import { ChatIcon, ArrowRightIcon } from './icons.jsx'
import { getCurrentPhaseName, getOverallProgress, PHASE_BADGE_CLASSES } from '../utils/projectStats.js'

// ---------------------------------------------------------------------------
// ProjectCard
// ---------------------------------------------------------------------------
// One project summary shown on the Dashboard: name, current phase, a
// progress bar, its Slack channel if one was connected, and a link into
// the full ProjectOverview page.
// ---------------------------------------------------------------------------
export default function ProjectCard({ project }) {
  const phase = getCurrentPhaseName(project)
  const progress = getOverallProgress(project)

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-6">
      <div className="flex items-start justify-between gap-3">
        <h3 className="text-lg font-semibold text-slate-900">{project.name}</h3>
        <span
          className={`shrink-0 rounded-full px-3 py-1 text-xs font-semibold ${PHASE_BADGE_CLASSES[phase]}`}
        >
          {phase}
        </span>
      </div>
      <p className="mt-2 line-clamp-2 text-sm text-slate-500">
        {project.description || 'No description provided.'}
      </p>

      <div className="mt-4">
        <div className="flex items-center justify-between text-sm">
          <span className="text-slate-500">Overall Progress</span>
          <span className="font-medium text-slate-900">{progress}%</span>
        </div>
        <div className="mt-1.5 h-2 rounded-full bg-slate-100">
          <div
            className="h-2 rounded-full bg-teal-500 transition-all"
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>

      {project.integrations?.slack && (
        <div className="mt-3 flex items-center gap-2 text-sm text-slate-500">
          <ChatIcon className="h-4 w-4" />
          Slack: {project.integrations.slack}
        </div>
      )}

      <Link
        to={`/projects/${project.id}`}
        className="mt-5 inline-flex items-center gap-2 rounded-lg bg-teal-500 px-4 py-2 text-sm font-semibold text-white transition hover:bg-teal-400"
      >
        View Project
        <ArrowRightIcon className="h-4 w-4" />
      </Link>
    </div>
  )
}
