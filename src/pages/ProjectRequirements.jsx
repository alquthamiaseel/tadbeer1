import { Link, useParams } from 'react-router-dom'
import { useProjects } from '../context/ProjectsContext.jsx'
import ComingSoon from './ComingSoon.jsx'

// Requirements extraction isn't built yet - this just moves the existing
// placeholder under the project-scoped route so Quick Actions and the
// sidebar link somewhere real per-project, without inventing content.
export default function ProjectRequirements() {
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

  return <ComingSoon title={`Requirements — ${project.name}`} />
}
