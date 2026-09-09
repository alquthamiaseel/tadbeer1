import { useAuth } from '../context/AuthContext.jsx'
import StatCard from '../components/StatCard.jsx'
import {
  FolderIcon,
  CheckCircleIcon,
  ClockIcon,
  GitBranchIcon,
  PlusIcon,
} from '../components/icons.jsx'

// The 4 summary cards shown at the top of the dashboard. This is just
// display data (icon, label, color) - no numbers, since there is no real
// project data behind this yet. Add a `value` field here once there is.
const stats = [
  { label: 'Active Projects', icon: FolderIcon, iconColorClass: 'bg-teal-50 text-teal-600' },
  { label: 'Approved Items', icon: CheckCircleIcon, iconColorClass: 'bg-green-50 text-green-600' },
  { label: 'Pending Review', icon: ClockIcon, iconColorClass: 'bg-amber-50 text-amber-600' },
  { label: 'Total Diagrams', icon: GitBranchIcon, iconColorClass: 'bg-purple-50 text-purple-600' },
]

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

  // Use the first name only for a friendlier greeting, e.g. "Ahmed"
  // instead of "Ahmed Al-Rashid".
  const firstName = user?.fullName?.split(' ')[0] || 'there'

  return (
    <div>
      {/* Dynamic greeting + today's date */}
      <h1 className="text-3xl font-bold text-slate-900">
        {getTimeOfDayGreeting()}, {firstName}
      </h1>
      <p className="mt-1 text-slate-500">{getTodayFormatted()}</p>

      {/* 4 empty summary cards - no numbers until real project data exists */}
      <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {stats.map((stat) => (
          <StatCard key={stat.label} {...stat} />
        ))}
      </div>

      {/* Main content row: "no projects yet" panel + empty recent activity */}
      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Left panel: takes up 2/3 of the row on large screens */}
        <div className="flex flex-col items-center justify-center rounded-2xl border border-slate-200 bg-white p-12 text-center lg:col-span-2">
          <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-slate-100">
            <FolderIcon className="h-7 w-7 text-slate-400" />
          </div>
          <h2 className="text-lg font-semibold text-slate-900">
            You have no current projects
          </h2>
          <p className="mt-1 text-slate-500">
            Get started by creating your first project.
          </p>
          <button className="mt-5 flex items-center gap-2 rounded-lg bg-teal-500 px-5 py-2.5 font-semibold text-white transition hover:bg-teal-400">
            <PlusIcon className="h-4 w-4" />
            New Project
          </button>
        </div>

        {/* Right panel: Recent Activity, empty for now */}
        <div className="rounded-2xl border border-slate-200 bg-white p-6">
          <h2 className="mb-4 font-semibold text-slate-900">Recent Activity</h2>
          <p className="text-sm text-slate-500">No recent activity yet.</p>
        </div>
      </div>
    </div>
  )
}
