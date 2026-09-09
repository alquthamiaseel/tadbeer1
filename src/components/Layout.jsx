import { Outlet } from 'react-router-dom'
import Sidebar from './Sidebar.jsx'

// ---------------------------------------------------------------------------
// Layout
// ---------------------------------------------------------------------------
// Shared shell for every "logged in" page: the sidebar stays fixed on the
// left, and whichever page is active (Dashboard, Profile, ...) renders in
// the space to the right via <Outlet />. This means the sidebar only has
// to be written once instead of being copy-pasted into every page.
// ---------------------------------------------------------------------------
export default function Layout() {
  return (
    <div className="flex min-h-screen bg-slate-100">
      <Sidebar />
      <main className="flex-1 overflow-y-auto p-8">
        <Outlet />
      </main>
    </div>
  )
}
