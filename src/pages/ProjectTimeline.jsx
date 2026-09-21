import { Link, useParams } from 'react-router-dom'
import { useProjects } from '../context/ProjectsContext.jsx'
import { PROJECT_PHASES } from '../context/ProjectsContext.jsx'
import { getPhaseStatus, getPendingDiagramsCount } from '../utils/projectStats.js'
import StatCard from '../components/StatCard.jsx'
import {
  CheckCircleIcon,
  ClockIcon,
  CalendarIcon,
  GitBranchIcon,
  PlusIcon,
  ChatIcon,
  DocumentIcon,
} from '../components/icons.jsx'

// One icon per activity type, so the feed doesn't show the same chat
// bubble for a GitHub link as it does for a Slack channel.
const ACTIVITY_ICONS = {
  created: PlusIcon,
  slack: ChatIcon,
  asana: DocumentIcon,
  github: GitBranchIcon,
}

function formatDateTime(iso) {
  return new Date(iso).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

// ---------------------------------------------------------------------------
// ProjectTimeline
// ---------------------------------------------------------------------------
// The 4 stat cards and the activity feed are both derived entirely from
// real project data - phase progress (already tracked on the project) and
// the activity log written in ProjectsContext.addProject. Nothing here is
// invented: a brand new project shows exactly 1 "Completed" (itself being
// created), 1 "In Progress" (its current phase), and 0 for anything that
// hasn't happened.
// ---------------------------------------------------------------------------
export default function ProjectTimeline() {
  const { id } = useParams()
  const { getProject } = useProjects()
  const project = getProject(id)

  if (!project) {
    return (
      <div>
        <h1 className="text-3xl font-bold text-slate-900">Project not found</h1>
        <p className="mt-1 text-slate-500">
          This project may have been removed.{' '}
          <Link to="/dashboard" className="font-medium text-teal-600 hover:text-teal-500">
            Back to Dashboard
          </Link>
        </p>
      </div>
    )
  }

  const completedPhases = PROJECT_PHASES.filter(
    (_phase, index) => getPhaseStatus(project, index) === 'complete',
  ).length
  const upcomingPhases = PROJECT_PHASES.filter(
    (_phase, index) => getPhaseStatus(project, index) === 'upcoming',
  ).length

  const stats = [
    {
      label: 'Completed',
      icon: CheckCircleIcon,
      iconColorClass: 'bg-green-50 text-green-600',
      value: completedPhases,
    },
    {
      label: 'In Progress',
      icon: ClockIcon,
      iconColorClass: 'bg-amber-50 text-amber-600',
      value: 1, // there's always exactly one current phase
    },
    {
      label: 'Pending Review',
      icon: GitBranchIcon,
      iconColorClass: 'bg-blue-50 text-blue-600',
      value: getPendingDiagramsCount(project),
    },
    {
      label: 'Upcoming',
      icon: CalendarIcon,
      iconColorClass: 'bg-slate-100 text-slate-500',
      value: upcomingPhases,
    },
  ]

  const activity = [...project.activity].sort((a, b) => new Date(b.createdAt) - new Date(a.createdAt))

  return (
    <div>
      <h1 className="text-3xl font-bold text-slate-900">Project Timeline</h1>
      <p className="mt-1 text-slate-500">Track the progress of {project.name}</p>

      <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {stats.map((stat) => (
          <StatCard key={stat.label} {...stat} />
        ))}
      </div>

      <div className="mt-6 rounded-2xl border border-slate-200 bg-white p-6">
        <h2 className="font-semibold text-slate-900">Activity Timeline</h2>
        <p className="mt-1 text-sm text-slate-500">All project events and AI actions</p>

        <ul className="mt-5 space-y-5">
          {activity.map((entry) => {
            const Icon = ACTIVITY_ICONS[entry.type] || PlusIcon
            return (
              <li key={entry.id} className="flex items-start gap-4">
                <div className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-teal-50 text-teal-600">
                  <Icon className="h-4 w-4" />
                </div>
                <div className="flex-1">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="font-medium text-slate-900">{entry.title}</p>
                    <div className="flex items-center gap-3">
                      <span className="rounded-full bg-green-50 px-2.5 py-0.5 text-xs font-semibold text-green-600">
                        Completed
                      </span>
                      <span className="text-sm text-slate-400">{formatDateTime(entry.createdAt)}</span>
                    </div>
                  </div>
                  <p className="text-sm text-slate-500">{entry.description}</p>
                </div>
              </li>
            )
          })}
        </ul>
      </div>
    </div>
  )
}
