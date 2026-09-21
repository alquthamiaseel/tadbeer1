import { createContext, useContext, useEffect, useState } from 'react'
import { useAuth } from './AuthContext.jsx'

// ---------------------------------------------------------------------------
// ProjectsContext
// ---------------------------------------------------------------------------
// Same "no real backend" approach as AuthContext: projects live in React
// state and are mirrored to localStorage so they survive a page refresh.
// This also owns the "New Project" modal's open/closed state, since both
// the Sidebar button and the Dashboard's empty-state button need to open
// the same modal without threading props through Layout.
// ---------------------------------------------------------------------------

const ProjectsContext = createContext(null)

const STORAGE_KEY = 'tadbeer_projects'

export const PROJECT_PHASES = ['Planning', 'Requirements', 'Design', 'Development', 'Review']

// There is no real Asana integration - this stands in for "pull the
// project's members from Asana" so a newly created project shows up with
// a believable, non-empty team instead of just the person who made it.
const ASANA_TEAM_POOL = [
  { name: 'Sara Hassan', role: 'UI/UX Designer' },
  { name: 'Mohammed Ali', role: 'Backend Engineer' },
  { name: 'Fatima Khan', role: 'QA Engineer' },
  { name: 'Omar Siddiqui', role: 'Frontend Engineer' },
  { name: 'Layla Ahmed', role: 'Business Analyst' },
  { name: 'Yousef Nasser', role: 'DevOps Engineer' },
]

function getInitials(fullName) {
  if (!fullName) return '?'
  return fullName
    .split(' ')
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0].toUpperCase())
    .join('')
}

// Picks 2-4 random, non-repeating members from the mock Asana pool.
function pullTeamFromAsana() {
  const shuffled = [...ASANA_TEAM_POOL].sort(() => Math.random() - 0.5)
  const count = 2 + Math.floor(Math.random() * 3) // 2, 3, or 4
  return shuffled.slice(0, count).map((member) => ({
    ...member,
    initials: getInitials(member.name),
  }))
}

export function ProjectsProvider({ children }) {
  const { user } = useAuth()
  const [projects, setProjects] = useState(() => {
    const saved = localStorage.getItem(STORAGE_KEY)
    return saved ? JSON.parse(saved) : []
  })
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false)

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(projects))
  }, [projects])

  // Builds a full project record from just the 3 wizard steps' inputs -
  // the phase timeline, mock Asana team, and activity metrics all start
  // from a believable "just created" state rather than fake numbers.
  function addProject({ name, description, methodology, integrations }) {
    const now = new Date().toISOString()
    const owner = { name: user?.fullName || 'Unknown', role: 'Project Manager', initials: getInitials(user?.fullName) }

    const project = {
      id: crypto.randomUUID(),
      name,
      description,
      methodology,
      integrations,
      currentPhaseIndex: 0, // index into PROJECT_PHASES - starts at "Planning"
      currentPhaseProgress: 15,
      team: [owner, ...pullTeamFromAsana()],
      diagramsCount: 0,
      approvedItems: 0,
      pendingReview: 0,
      createdAt: now,
      updatedAt: now,
    }

    setProjects((previous) => [project, ...previous])
    return project
  }

  function getProject(id) {
    return projects.find((project) => project.id === id)
  }

  const value = {
    projects,
    addProject,
    getProject,
    isCreateModalOpen,
    openCreateModal: () => setIsCreateModalOpen(true),
    closeCreateModal: () => setIsCreateModalOpen(false),
  }

  return <ProjectsContext.Provider value={value}>{children}</ProjectsContext.Provider>
}

export function useProjects() {
  return useContext(ProjectsContext)
}
