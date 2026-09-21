import { useAuth } from '../context/AuthContext.jsx'
import { useProjects } from '../context/ProjectsContext.jsx'
import StatCard from '../components/StatCard.jsx'
import ProjectCard from '../components/ProjectCard.jsx'
import { getApprovedDiagramsCount, getPendingDiagramsCount } from '../utils/projectStats.js'
import {
  FolderIcon,
  CheckCircleIcon,
  ClockIcon,
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

// Picks "morning" / "afternoon" / "evening" based on the current hour.
function getTimeOfDayGreeting() {
  const hour = new Date().getHours()
  if (hour < 12) return 'Good morning'
  if (hour < 18) return 'Good afternoon'
  return 'Good evening'
}

// Formats today's date as e.g. "Wednesday, May 6, 2026".
function getTodayFormatted() {
  return new Date().toLocaleDateString('en-US', {
    weekday: 'long',
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  })
}

export default function Dashboard() {
  const { user } = useAuth()
  const { projects, openCreateModal } = useProjects()

  // Use the first name only for a friendlier greeting, e.g. "Ahmed"
  // instead of "Ahmed Al-Rashid".
  const firstName = user?.fullName?.split(' ')[0] || 'there'

  // The 4 summary cards are derived from real project data now that
  // projects can actually be created - a brand new account with no
  // projects still shows honest 0s instead of fake numbers.
  const stats = [
    {
      label: 'Active Projects',
      icon: FolderIcon,
      iconColorClass: 'bg-teal-50 text-teal-600',
      value: projects.length,
    },
    {
      label: 'Approved Items',
      icon: CheckCircleIcon,
      iconColorClass: 'bg-green-50 text-green-600',
      value: projects.reduce((sum, project) => sum + getApprovedDiagramsCount(project), 0),
    },
    {
      label: 'Pending Review',
      icon: ClockIcon,
      iconColorClass: 'bg-amber-50 text-amber-600',
      value: projects.reduce((sum, project) => sum + getPendingDiagramsCount(project), 0),
    },
    {
      label: 'Total Diagrams',
      icon: GitBranchIcon,
      iconColorClass: 'bg-purple-50 text-purple-600',
      value: projects.reduce((sum, project) => sum + project.diagrams.length, 0),
    },
  ]

  // Every project's real activity log, flattened and sorted newest first -
  // not just "created" entries, but integrations added too.
  const recentActivity = projects
    .flatMap((project) => project.activity.map((entry) => ({ ...entry, projectName: project.name })))
    .sort((a, b) => new Date(b.createdAt) - new Date(a.createdAt))
    .slice(0, 5)

  return (
    <div>
      {/* Dynamic greeting + today's date */}
      <h1 className="text-3xl font-bold text-slate-900">
        {getTimeOfDayGreeting()}, {firstName}
      </h1>
      <p className="mt-1 text-slate-500">{getTodayFormatted()}</p>

      <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {stats.map((stat) => (
          <StatCard key={stat.label} {...stat} />
        ))}
      </div>

      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Left column: takes up 2/3 of the row on large screens */}
        <div className="space-y-4 lg:col-span-2">
          {projects.length === 0 ? (
            <div className="flex flex-col items-center justify-center rounded-2xl border border-slate-200 bg-white p-12 text-center">
              <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-slate-100">
                <FolderIcon className="h-7 w-7 text-slate-400" />
              </div>
              <h2 className="text-lg font-semibold text-slate-900">
                You have no current projects
              </h2>
              <p className="mt-1 text-slate-500">
                Get started by creating your first project.
              </p>
              <button
                onClick={openCreateModal}
                className="mt-5 flex items-center gap-2 rounded-lg bg-teal-500 px-5 py-2.5 font-semibold text-white transition hover:bg-teal-400"
              >
                <PlusIcon className="h-4 w-4" />
                New Project
              </button>
            </div>
          ) : (
            projects.map((project) => <ProjectCard key={project.id} project={project} />)
          )}
        </div>

        {/* Right panel: Recent Activity */}
        <div className="rounded-2xl border border-slate-200 bg-white p-6">
          <h2 className="mb-4 font-semibold text-slate-900">Recent Activity</h2>
          {recentActivity.length === 0 ? (
            <p className="text-sm text-slate-500">No recent activity yet.</p>
          ) : (
            <ul className="space-y-4">
              {recentActivity.map((entry) => {
                const Icon = ACTIVITY_ICONS[entry.type] || PlusIcon
                return (
                  <li key={entry.id} className="flex items-start gap-3 text-sm">
                    <div className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-teal-50 text-teal-600">
                      <Icon className="h-3.5 w-3.5" />
                    </div>
                    <div>
                      <p className="text-slate-700">
                        <span className="font-medium text-slate-900">{entry.projectName}</span> —{' '}
                        {entry.description}
                      </p>
                    </div>
                  </li>
                )
              })}
            </ul>
          )}
        </div>
      </div>
    </div>
  )
}
