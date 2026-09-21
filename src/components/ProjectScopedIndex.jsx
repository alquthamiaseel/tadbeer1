import { Navigate } from 'react-router-dom'
import { useProjects } from '../context/ProjectsContext.jsx'
import { FolderIcon, PlusIcon } from './icons.jsx'

// ---------------------------------------------------------------------------
// ProjectScopedIndex
// ---------------------------------------------------------------------------
// Shared by the flat sidebar routes (/project-overview, /diagrams,
// /requirements, /timeline) that don't know which project to show, since
// there's no project switcher yet. If the user has at least one project,
// jump straight to the most recently created one's version of that page
// (appending `pathSuffix`); otherwise prompt them to create their first
// project.
// ---------------------------------------------------------------------------
export default function ProjectScopedIndex({ title, pathSuffix = '' }) {
  const { projects, openCreateModal } = useProjects()

  if (projects.length > 0) {
    return <Navigate to={`/projects/${projects[0].id}${pathSuffix}`} replace />
  }

  return (
    <div>
      <h1 className="text-3xl font-bold text-slate-900">{title}</h1>
      <div className="mt-6 flex flex-col items-center justify-center rounded-2xl border border-dashed border-slate-300 bg-white p-12 text-center">
        <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-slate-100">
          <FolderIcon className="h-7 w-7 text-slate-400" />
        </div>
        <p className="text-slate-500">You don't have any projects yet.</p>
        <button
          onClick={openCreateModal}
          className="mt-4 flex items-center gap-2 rounded-lg bg-teal-500 px-5 py-2.5 font-semibold text-white transition hover:bg-teal-400"
        >
          <PlusIcon className="h-4 w-4" />
          New Project
        </button>
      </div>
    </div>
  )
}
