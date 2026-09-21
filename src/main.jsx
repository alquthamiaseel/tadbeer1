import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import './index.css'
import App from './App.jsx'
import { AuthProvider } from './context/AuthContext.jsx'
import { ProjectsProvider } from './context/ProjectsContext.jsx'

// This is the entry point of the whole app.
// - BrowserRouter enables page navigation (e.g. /login, /dashboard).
// - AuthProvider stores "who is logged in" so any page can read/update it.
// - ProjectsProvider stores the user's projects, and reads the current
//   user from AuthProvider (to tag a project's owner), so it must be
//   nested inside it.
createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <ProjectsProvider>
          <App />
        </ProjectsProvider>
      </AuthProvider>
    </BrowserRouter>
  </StrictMode>,
)
