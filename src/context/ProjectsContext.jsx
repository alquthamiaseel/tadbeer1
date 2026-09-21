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

function getInitials(fullName) {
  if (!fullName) return '?'
  return fullName
    .split(' ')
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0].toUpperCase())
    .join('')
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

  // Every real, user-caused thing that happens to a project is logged here
  // - this is what the Timeline page reads. Only things that actually
  // happened get logged (a typed-in integration field), never a claim
  // that something is "connected" or "monitoring", since neither is true
  // without a real backend.
  function logActivity(type, title, description) {
    return { id: crypto.randomUUID(), type, title, description, createdAt: new Date().toISOString() }
  }

  // Builds a full project record from just the 3 wizard steps' inputs.
  // There's no real Asana integration yet, so `team` only ever holds the
  // person who actually created the project - it must never be filled
  // with invented names. Once a real Asana connection exists, this is
  // where its members would be fetched in and added.
  //
  // `diagrams` starts empty and stays empty until there's a real AI agent
  // producing them - nothing in this app ever seeds it with invented
  // diagrams. Total/approved/pending diagram counts are always derived
  // from this array (see utils/projectStats.js), never stored separately,
  // so there's only one source of truth for "how many diagrams exist".
  function addProject({ name, description, methodology, integrations }) {
    const now = new Date().toISOString()
    const owner = { name: user?.fullName || 'Unknown', role: 'Project Manager', initials: getInitials(user?.fullName) }

    const activity = [logActivity('created', 'Project Created', `${name} was initialized`)]
    if (integrations.slack) {
      activity.push(logActivity('slack', 'Slack Channel Added', `${integrations.slack} was added to the project`))
    }
    if (integrations.asana) {
      activity.push(logActivity('asana', 'Asana Project Linked', `${integrations.asana} was linked to the project`))
    }
    if (integrations.github) {
      activity.push(logActivity('github', 'GitHub Repository Linked', `${integrations.github} was linked to the project`))
    }

    const project = {
      id: crypto.randomUUID(),
      name,
      description,
      methodology,
      integrations,
      currentPhaseIndex: 0, // index into PROJECT_PHASES - starts at "Planning"
      currentPhaseProgress: 0, // nothing has happened yet - no work to show progress on
      team: [owner],
      diagrams: [],
      activity,
      createdAt: now,
      updatedAt: now,
    }

    setProjects((previous) => [project, ...previous])
    return project
  }

  function getProject(id) {
    return projects.find((project) => project.id === id)
  }

  // Used by Settings' Danger Zone. Irreversible, so the confirm prompt
  // lives at the call site right before the button triggers this.
  function deleteAllProjects() {
    setProjects([])
  }

  const value = {
    projects,
    addProject,
    getProject,
    deleteAllProjects,
    isCreateModalOpen,
    openCreateModal: () => setIsCreateModalOpen(true),
    closeCreateModal: () => setIsCreateModalOpen(false),
  }

  return <ProjectsContext.Provider value={value}>{children}</ProjectsContext.Provider>
}

export function useProjects() {
  return useContext(ProjectsContext)
}
