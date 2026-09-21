import { Navigate, Route, Routes } from 'react-router-dom'
import Login from './pages/Login.jsx'
import Register from './pages/Register.jsx'
import Dashboard from './pages/Dashboard.jsx'
import Profile from './pages/Profile.jsx'
import ProjectOverview from './pages/ProjectOverview.jsx'
import ProjectDiagrams from './pages/ProjectDiagrams.jsx'
import ProjectRequirements from './pages/ProjectRequirements.jsx'
import ProjectTimeline from './pages/ProjectTimeline.jsx'
import Settings from './pages/Settings.jsx'
import Layout from './components/Layout.jsx'
import ProtectedRoute from './components/ProtectedRoute.jsx'
import ProjectScopedIndex from './components/ProjectScopedIndex.jsx'

// ---------------------------------------------------------------------------
// App
// ---------------------------------------------------------------------------
// All page routing lives here. There are two groups of routes:
//
// 1. Public pages (Login, Register) - no sidebar, full-screen forms.
// 2. Private pages (Dashboard, Profile, ...) - wrapped in <Layout>, which
//    adds the sidebar, and in <ProtectedRoute>, which redirects to /login
//    if nobody is signed in.
//
// Project Overview, Diagrams, Requirements, and Timeline are all
// project-scoped (/projects/:id/...), since none of them make sense
// without a project to show. The flat sidebar links (/project-overview,
// /diagrams, /requirements, /timeline) redirect to the most recently
// created project's version of that page via ProjectScopedIndex.
// Settings stays a single account-level page - it isn't project-scoped.
// ---------------------------------------------------------------------------
export default function App() {
  return (
    <Routes>
      {/* Public routes */}
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />

      {/* Private routes - all share the sidebar layout */}
      <Route
        element={
          <ProtectedRoute>
            <Layout />
          </ProtectedRoute>
        }
      >
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/profile" element={<Profile />} />
        <Route path="/settings" element={<Settings />} />

        <Route path="/projects/:id" element={<ProjectOverview />} />
        <Route path="/projects/:id/diagrams" element={<ProjectDiagrams />} />
        <Route path="/projects/:id/requirements" element={<ProjectRequirements />} />
        <Route path="/projects/:id/timeline" element={<ProjectTimeline />} />

        {/* Sidebar links - jump to the most recent project's version of each page */}
        <Route
          path="/project-overview"
          element={<ProjectScopedIndex title="Project Overview" />}
        />
        <Route
          path="/diagrams"
          element={<ProjectScopedIndex title="System Diagrams" pathSuffix="/diagrams" />}
        />
        <Route
          path="/requirements"
          element={<ProjectScopedIndex title="Requirements" pathSuffix="/requirements" />}
        />
        <Route
          path="/timeline"
          element={<ProjectScopedIndex title="Project Timeline" pathSuffix="/timeline" />}
        />
      </Route>

      {/* Any unknown path redirects to the login page */}
      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes>
  )
}
