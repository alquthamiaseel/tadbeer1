import { Link, useParams } from 'react-router-dom'
import { useProjects } from '../context/ProjectsContext.jsx'
import { PROJECT_PHASES } from '../context/ProjectsContext.jsx'
import {
  getPhaseStatus,
  getPhaseProgress,
  getOverallProgress,
  PHASE_BADGE_CLASSES,
} from '../utils/projectStats.js'
import {
  CheckCircleIcon,
  ClockIcon,
  ChatIcon,
  DocumentIcon,
  GitBranchIcon,
  ExternalLinkIcon,
  UsersIcon,
  CalendarIcon,
  ListIcon,
} from '../components/icons.jsx'

// One step in the "Project Phases" row: a status icon, the phase name,
// and a thin progress bar underneath it.
function PhaseStep({ name, status, progress }) {
  return (
    <div className="flex-1">
      <div className="flex items-center gap-2">
        {status === 'complete' && <CheckCircleIcon className="h-5 w-5 shrink-0 text-green-500" />}
        {status === 'current' && <ClockIcon className="h-5 w-5 shrink-0 text-teal-500" />}
        {status === 'upcoming' && (
          <span className="h-5 w-5 shrink-0 rounded-full border-2 border-slate-300" />
        )}
        <span
          className={`text-sm font-medium ${status === 'upcoming' ? 'text-slate-400' : 'text-slate-900'}`}
        >
          {name}
        </span>
      </div>
      <div className="mt-2 h-1.5 rounded-full bg-slate-100">
        <div
          className={`h-1.5 rounded-full transition-all ${
            status === 'complete' ? 'bg-green-500' : 'bg-teal-500'
          }`}
          style={{ width: `${progress}%` }}
        />
      </div>
    </div>
  )
}

// One row in the Integrations card. Values typed as a full URL become a
// real link; anything else (a channel name, a project title) is just
// shown as text since there's nowhere real for it to link to.
function IntegrationRow({ icon: Icon, label, value }) {
  const isLink = value?.startsWith('http')
  return (
    <div className="flex items-center justify-between border-b border-slate-100 py-3 last:border-b-0">
      <div className="flex items-center gap-3">
        <Icon className="h-4 w-4 shrink-0 text-slate-400" />
        <div>
          <p className="text-sm font-medium text-slate-900">{label}</p>
          <p className="text-sm text-slate-500">{value || 'Not connected'}</p>
        </div>
      </div>
      {isLink && (
        <a
          href={value}
          target="_blank"
          rel="noopener noreferrer"
          className="text-slate-400 transition hover:text-teal-500"
        >
          <ExternalLinkIcon className="h-4 w-4" />
        </a>
      )}
    </div>
  )
}

const QUICK_ACTIONS = [
  { label: 'View Diagrams', to: '/diagrams', primary: true },
  { label: 'View Requirements', to: '/requirements' },
  { label: 'View Timeline', to: '/timeline' },
]

export default function ProjectOverview() {
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

  const currentPhase = PROJECT_PHASES[project.currentPhaseIndex]
  const overallProgress = getOverallProgress(project)

  return (
    <div>
      {/* Header: name, current phase badge, methodology pill */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <h1 className="text-3xl font-bold text-slate-900">{project.name}</h1>
          <span
            className={`rounded-full px-3 py-1 text-xs font-semibold ${PHASE_BADGE_CLASSES[currentPhase]}`}
          >
            {currentPhase}
          </span>
        </div>
        <span className="rounded-full border border-slate-200 px-3 py-1 text-sm font-medium text-slate-700">
          {project.methodology}
        </span>
      </div>
      <p className="mt-2 max-w-3xl text-slate-500">
        {project.description || 'No description provided.'}
      </p>

      {/* Project Phases */}
      <div className="mt-6 rounded-2xl border border-slate-200 bg-white p-6">
        <h2 className="font-semibold text-slate-900">Project Phases</h2>
        <p className="mt-1 text-sm text-slate-500">Current phase: {currentPhase}</p>

        <div className="mt-5 flex items-start gap-4 overflow-x-auto pb-1">
          {PROJECT_PHASES.map((name, index) => (
            <PhaseStep
              key={name}
              name={name}
              status={getPhaseStatus(project, index)}
              progress={getPhaseProgress(project, index)}
            />
          ))}
        </div>
      </div>

      {/* Integrations / Team Members / Timeline */}
      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="rounded-2xl border border-slate-200 bg-white p-6">
          <h2 className="mb-1 font-semibold text-slate-900">Integrations</h2>
          <div className="mt-3">
            <IntegrationRow icon={ChatIcon} label="Slack" value={project.integrations.slack} />
            <IntegrationRow icon={DocumentIcon} label="Asana" value={project.integrations.asana} />
            <IntegrationRow icon={GitBranchIcon} label="GitHub" value={project.integrations.github} />
          </div>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-6">
          <div className="mb-3 flex items-center gap-2">
            <UsersIcon className="h-5 w-5 text-slate-400" />
            <h2 className="font-semibold text-slate-900">Team Members</h2>
          </div>
          <div className="space-y-3">
            {project.team.map((member) => (
              <div key={member.name} className="flex items-center gap-3">
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-teal-50 text-sm font-semibold text-teal-700">
                  {member.initials}
                </div>
                <p className="font-medium text-slate-900">{member.name}</p>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-6">
          <div className="mb-3 flex items-center gap-2">
            <CalendarIcon className="h-5 w-5 text-slate-400" />
            <h2 className="font-semibold text-slate-900">Timeline</h2>
          </div>

          <p className="text-sm text-slate-500">Created</p>
          <p className="font-medium text-slate-900">{project.createdAt.slice(0, 10)}</p>

          <p className="mt-3 text-sm text-slate-500">Last Updated</p>
          <p className="font-medium text-slate-900">{project.updatedAt.slice(0, 10)}</p>

          <p className="mt-3 text-sm text-slate-500">Progress</p>
          <div className="mt-1.5 flex items-center gap-2">
            <div className="h-2 flex-1 rounded-full bg-slate-100">
              <div
                className="h-2 rounded-full bg-teal-500 transition-all"
                style={{ width: `${overallProgress}%` }}
              />
            </div>
            <span className="text-sm font-medium text-slate-900">{overallProgress}%</span>
          </div>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="mt-6 rounded-2xl border border-slate-200 bg-white p-6">
        <div className="mb-4 flex items-center gap-2">
          <ListIcon className="h-5 w-5 text-slate-400" />
          <h2 className="font-semibold text-slate-900">Quick Actions</h2>
        </div>
        <div className="flex flex-wrap gap-3">
          {QUICK_ACTIONS.map(({ label, to, primary }) => (
            <Link
              key={to}
              to={to}
              className={
                primary
                  ? 'rounded-lg bg-teal-500 px-5 py-2.5 font-semibold text-white transition hover:bg-teal-400'
                  : 'rounded-lg border border-slate-200 px-5 py-2.5 font-semibold text-slate-700 transition hover:bg-slate-50'
              }
            >
              {label}
            </Link>
          ))}
        </div>
      </div>
    </div>
  )
}
