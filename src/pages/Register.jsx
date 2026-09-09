import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import FormField from '../components/FormField.jsx'
import {
  UserIcon,
  PhoneIcon,
  MapPinIcon,
  BriefcaseIcon,
  MailIcon,
  LockIcon,
} from '../components/icons.jsx'
import { useAuth } from '../context/AuthContext.jsx'

// ---------------------------------------------------------------------------
// Register page ("Create Account")
// ---------------------------------------------------------------------------
// Collects the new user's details in a two-column form (matches the
// provided design) and, on submit, saves them as the current user and
// redirects to the dashboard - same pattern as the Login page.
// ---------------------------------------------------------------------------

// Starting values for every field in the form, kept in one object so the
// component only needs a single piece of state instead of one per field.
const emptyForm = {
  fullName: '',
  phoneNumber: '',
  location: '',
  department: '',
  email: '',
  password: '',
  confirmPassword: '',
}

export default function Register() {
  const [form, setForm] = useState(emptyForm)
  const { register } = useAuth()
  const navigate = useNavigate()

  // Generic change handler shared by every field: it updates just the one
  // key in `form` that matches the input's `name` attribute.
  function handleChange(event) {
    const { name, value } = event.target
    setForm((previous) => ({ ...previous, [name]: value }))
  }

  function handleSubmit(event) {
    event.preventDefault()

    if (form.password !== form.confirmPassword) {
      alert('Passwords do not match.')
      return
    }

    register({
      fullName: form.fullName,
      email: form.email,
      phoneNumber: form.phoneNumber,
      location: form.location,
      department: form.department,
    })
    navigate('/dashboard')
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-950 px-4 py-10">
      {/* Card container - wider than the login card to fit two columns */}
      <div className="w-full max-w-2xl rounded-2xl border border-slate-800 bg-slate-900 p-8 shadow-2xl">
        <h1 className="text-3xl font-bold text-white">Create Account</h1>
        <p className="mt-2 text-slate-400">Sign up to get started</p>

        <form className="mt-8 space-y-5" onSubmit={handleSubmit}>
          {/* Two-column grid on medium screens and up, single column on mobile */}
          <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
            <FormField
              label="Full Name"
              icon={UserIcon}
              name="fullName"
              placeholder="Ahmed Al-Rashid"
              value={form.fullName}
              onChange={handleChange}
            />
            <FormField
              label="Phone Number"
              icon={PhoneIcon}
              name="phoneNumber"
              placeholder="+971 50 123 4567"
              value={form.phoneNumber}
              onChange={handleChange}
            />
            <FormField
              label="Location"
              icon={MapPinIcon}
              name="location"
              placeholder="Dubai, UAE"
              value={form.location}
              onChange={handleChange}
            />
            <FormField
              label="Department"
              icon={BriefcaseIcon}
              name="department"
              placeholder="Engineering"
              value={form.department}
              onChange={handleChange}
            />
          </div>

          {/* Email spans the full width by itself */}
          <FormField
            label="Email Address"
            icon={MailIcon}
            type="email"
            name="email"
            placeholder="ahmed@example.com"
            value={form.email}
            onChange={handleChange}
          />

          <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
            <FormField
              label="Password"
              icon={LockIcon}
              type="password"
              name="password"
              placeholder="Create a strong password"
              value={form.password}
              onChange={handleChange}
            />
            <FormField
              label="Confirm Password"
              icon={LockIcon}
              type="password"
              name="confirmPassword"
              placeholder="Re-enter your password"
              value={form.confirmPassword}
              onChange={handleChange}
            />
          </div>

          <button
            type="submit"
            className="w-full rounded-lg bg-teal-500 py-3 font-semibold text-white transition hover:bg-teal-400"
          >
            Create Account
          </button>
        </form>

        <p className="mt-6 text-center text-slate-400">
          Already have an account?{' '}
          <Link to="/login" className="font-medium text-teal-400 hover:text-teal-300">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  )
}
