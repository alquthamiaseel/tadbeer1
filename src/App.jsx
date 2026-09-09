import { Navigate, Route, Routes } from 'react-router-dom'
import Login from './pages/Login.jsx'
import Register from './pages/Register.jsx'
import Dashboard from './pages/Dashboard.jsx'
import Profile from './pages/Profile.jsx'
import ComingSoon from './pages/ComingSoon.jsx'
import Layout from './components/Layout.jsx'
import ProtectedRoute from './components/ProtectedRoute.jsx'

// ---------------------------------------------------------------------------
// App
// ---------------------------------------------------------------------------
// All page routing lives here. There are two groups of routes:
//
// 1. Public pages (Login, Register) - no sidebar, full-screen forms.
// 2. Private pages (Dashboard, Profile, ...) - wrapped in <Layout>, which
//    adds the sidebar, and in <ProtectedRoute>, which redirects to /login
//    if nobody is signed in.
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

        {/* Sidebar links that don't have real pages yet */}
        <Route path="/project-overview" element={<ComingSoon title="Project Overview" />} />
        <Route path="/requirements" element={<ComingSoon title="Requirements" />} />
        <Route path="/diagrams" element={<ComingSoon title="Diagrams" />} />
        <Route path="/timeline" element={<ComingSoon title="Timeline" />} />
        <Route path="/settings" element={<ComingSoon title="Settings" />} />
      </Route>

      {/* Any unknown path redirects to the login page */}
      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes>
  )
}
