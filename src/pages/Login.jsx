import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import FormField from '../components/FormField.jsx'
import { MailIcon, LockIcon } from '../components/icons.jsx'
import { useAuth } from '../context/AuthContext.jsx'

// ---------------------------------------------------------------------------
// Login page
// ---------------------------------------------------------------------------
// A simple "Welcome Back" sign-in form. There is no backend yet, so
// submitting the form just stores the typed email as the "logged in
// user" (see AuthContext) and sends the user to the dashboard.
// ---------------------------------------------------------------------------
export default function Login() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const { login } = useAuth()
  const navigate = useNavigate()

  function handleSubmit(event) {
    event.preventDefault()
    login({ email })
    navigate('/dashboard')
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-950 px-4">
      {/* Card container */}
      <div className="w-full max-w-md rounded-2xl border border-slate-800 bg-slate-900 p-8 shadow-2xl">
        <h1 className="text-3xl font-bold text-white">Welcome Back</h1>
        <p className="mt-2 text-slate-400">Sign in to continue</p>

        <form className="mt-8 space-y-5" onSubmit={handleSubmit}>
          <FormField
            label="Email Address"
            icon={MailIcon}
            type="email"
            name="email"
            placeholder="ahmed@example.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />

          <FormField
            label="Password"
            icon={LockIcon}
            type="password"
            name="password"
            placeholder="Enter your password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />

          {/* Forgot password link, right aligned */}
          <div className="text-right">
            <a href="#" className="text-sm font-medium text-teal-400 hover:text-teal-300">
              Forgot password?
            </a>
          </div>

          <button
            type="submit"
            className="w-full rounded-lg bg-teal-500 py-3 font-semibold text-white transition hover:bg-teal-400"
          >
            Sign In
          </button>
        </form>

        <p className="mt-6 text-center text-slate-400">
          Don&apos;t have an account?{' '}
          <Link to="/register" className="font-medium text-teal-400 hover:text-teal-300">
            Sign up
          </Link>
        </p>
      </div>
    </div>
  )
}
