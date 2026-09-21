import { NavLink } from 'react-router-dom'
import {
  GridIcon,
  DocumentIcon,
  ListIcon,
  GitBranchIcon,
  CalendarIcon,
  SettingsIcon,
  PlusIcon,
} from './icons.jsx'
import { useAuth } from '../context/AuthContext.jsx'
import { useProjects } from '../context/ProjectsContext.jsx'

// The main navigation links shown in the middle of the sidebar.
// Kept as data (instead of copy/pasting a <NavLink> five times) so adding
// a new page later is just one more entry in this array.
const navItems = [
  { label: 'Dashboard', to: '/dashboard', icon: GridIcon },
  { label: 'Project Overview', to: '/project-overview', icon: DocumentIcon },
  { label: 'Requirements', to: '/requirements', icon: ListIcon },
  { label: 'Diagrams', to: '/diagrams', icon: GitBranchIcon },
  { label: 'Timeline', to: '/timeline', icon: CalendarIcon },
]

// Turns a full name like "Ahmed Al-Rashid" into initials like "AR",
// used for the little avatar circle at the bottom of the sidebar.
function getInitials(fullName) {
  if (!fullName) return '?'
  return fullName
    .split(' ')
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0].toUpperCase())
    .join('')
}

export default function Sidebar() {
  const { user } = useAuth()
  const { openCreateModal } = useProjects()

  return (
    <aside className="flex h-screen w-72 shrink-0 flex-col justify-between border-r border-slate-800 bg-slate-950 px-4 py-6">
      {/* Top section: logo + "New Project" button + main nav links */}
      <div>
        <div className="mb-6 flex items-center gap-3 px-2">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-teal-500 font-bold text-white">
            T
          </div>
          <div>
            <p className="font-semibold text-white">Tadbeer</p>
            <p className="text-xs text-slate-400">AI-Powered SDLC</p>
          </div>
        </div>

        <button
          onClick={openCreateModal}
          className="mb-6 flex w-full items-center justify-center gap-2 rounded-lg bg-teal-500 py-2.5 font-semibold text-white transition hover:bg-teal-400"
        >
          <PlusIcon className="h-4 w-4" />
          New Project
        </button>

        <nav className="space-y-1">
          {navItems.map(({ label, to, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition ${
                  isActive
                    ? 'bg-slate-800 text-white'
                    : 'text-slate-400 hover:bg-slate-900 hover:text-white'
                }`
              }
            >
              <Icon className="h-5 w-5" />
              {label}
            </NavLink>
          ))}
        </nav>
      </div>

      {/* Bottom section: settings + the current user's profile row */}
      <div className="space-y-1 border-t border-slate-800 pt-4">
        <NavLink
          to="/settings"
          className={({ isActive }) =>
            `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition ${
              isActive
                ? 'bg-slate-800 text-white'
                : 'text-slate-400 hover:bg-slate-900 hover:text-white'
            }`
          }
        >
          <SettingsIcon className="h-5 w-5" />
          Settings
        </NavLink>

        <NavLink
          to="/profile"
          className={({ isActive }) =>
            `flex items-center gap-3 rounded-lg px-3 py-2.5 transition ${
              isActive ? 'bg-slate-800' : 'hover:bg-slate-900'
            }`
          }
        >
          <div className="flex h-9 w-9 items-center justify-center rounded-full bg-teal-500 text-sm font-semibold text-white">
            {getInitials(user?.fullName)}
          </div>
          <div className="min-w-0">
            <p className="truncate text-sm font-medium text-white">
              {user?.fullName || 'Guest'}
            </p>
            <p className="truncate text-xs text-slate-400">Project Manager</p>
          </div>
        </NavLink>
      </div>
    </aside>
  )
}
