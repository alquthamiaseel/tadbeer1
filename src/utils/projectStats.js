import { PROJECT_PHASES } from '../context/ProjectsContext.jsx'

// ---------------------------------------------------------------------------
// projectStats
// ---------------------------------------------------------------------------
// Small pure helpers shared by ProjectCard and ProjectOverview so both
// read a project's phase/progress the same way instead of duplicating the
// "which phases are done" math in two components.
// ---------------------------------------------------------------------------

export function getPhaseStatus(project, index) {
  if (index < project.currentPhaseIndex) return 'complete'
  if (index === project.currentPhaseIndex) return 'current'
  return 'upcoming'
}

export function getPhaseProgress(project, index) {
  const status = getPhaseStatus(project, index)
  if (status === 'complete') return 100
  if (status === 'current') return project.currentPhaseProgress
  return 0
}

// Average of every phase's progress - a brand new project (only "Planning"
// started) sits in the low single digits, which is honest rather than
// showing an impressive-looking fake percentage.
export function getOverallProgress(project) {
  const total = PROJECT_PHASES.reduce((sum, _phase, index) => sum + getPhaseProgress(project, index), 0)
  return Math.round(total / PROJECT_PHASES.length)
}

export function getCurrentPhaseName(project) {
  return PROJECT_PHASES[project.currentPhaseIndex]
}

// Phase name -> badge color, shared by ProjectCard (Dashboard) and
// ProjectOverview so a project's phase reads the same color everywhere.
export const PHASE_BADGE_CLASSES = {
  Planning: 'bg-slate-100 text-slate-600',
  Requirements: 'bg-blue-50 text-blue-600',
  Design: 'bg-purple-50 text-purple-600',
  Development: 'bg-amber-50 text-amber-600',
  Review: 'bg-green-50 text-green-600',
}
