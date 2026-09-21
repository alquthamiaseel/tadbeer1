import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext.jsx'
import { useProjects } from '../context/ProjectsContext.jsx'
import { getReviewedDiagramsCount } from '../utils/projectStats.js'
import Toggle from '../components/Toggle.jsx'
import {
  UserIcon,
  MailIcon,
  PhoneIcon,
  MapPinIcon,
  BriefcaseIcon,
  CalendarIcon,
  LogoutIcon,
  PencilIcon,
  BellIcon,
} from '../components/icons.jsx'

// Same initials helper idea as the sidebar, used for the big avatar here.
function getInitials(fullName) {
  if (!fullName) return '?'
  return fullName
    .split(' ')
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0].toUpperCase())
    .join('')
}

function formatDate(iso) {
  if (!iso) return 'Not provided'
  return new Date(iso).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  })
}

// One row of the Personal Information grid. In edit mode, fields that
// were given a `name` (i.e. actually editable - not Email or Joined)
// render as an input instead of plain text.
function ProfileDetail({ icon: Icon, label, isEditing, name, value, display, onChange }) {
  return (
    <div>
      <p className="mb-1.5 flex items-center gap-2 text-sm text-slate-500">
        <Icon className="h-4 w-4" />
        {label}
      </p>
      {isEditing && name ? (
        <input
          name={name}
          value={value}
          onChange={onChange}
          className="w-full rounded-lg border border-slate-200 px-3 py-2 text-slate-900 outline-none focus:border-teal-400"
        />
      ) : (
        <p className="font-medium text-slate-900">{display || 'Not provided'}</p>
      )}
    </div>
  )
}

const emptyEditForm = { fullName: '', phoneNumber: '', location: '', department: '' }

export default function Profile() {
  const { user, logout, setUser } = useAuth()
  const { projects } = useProjects()
  const navigate = useNavigate()

  const [isEditing, setIsEditing] = useState(false)
  const [form, setForm] = useState(emptyEditForm)
  const [emailNotifications, setEmailNotifications] = useState(true)
  const [slackAlerts, setSlackAlerts] = useState(true)

  function handleLogout() {
    logout()
    navigate('/login')
  }

  function handleChange(event) {
    const { name, value } = event.target
    setForm((previous) => ({ ...previous, [name]: value }))
  }

  function startEditing() {
    setForm({
      fullName: user?.fullName || '',
      phoneNumber: user?.phoneNumber || '',
      location: user?.location || '',
      department: user?.department || '',
    })
    setIsEditing(true)
  }

  function handleSave() {
    setUser((previous) => ({ ...previous, ...form }))
    setIsEditing(false)
  }

  // Account Stats are derived from real project data - a fresh account
  // with no projects shows honest 0s rather than fake numbers.
  const uniqueTeamMembers = new Set(
    projects.flatMap((project) => project.team.map((member) => member.name)),
  ).size

  const accountStats = [
    { label: 'Projects Managed', value: projects.length },
    { label: 'Diagrams Reviewed', value: projects.reduce((sum, p) => sum + getReviewedDiagramsCount(p), 0) },
    // There's no Requirements feature yet to derive this from - stays a
    // real, honest 0 rather than being wired to an unrelated number.
    { label: 'Requirements Approved', value: 0 },
    { label: 'Team Members', value: uniqueTeamMembers },
  ]

  return (
    <div>
      <h1 className="text-3xl font-bold text-slate-900">Profile</h1>
      <p className="mt-1 text-slate-500">Manage your account settings and preferences</p>

      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Left: Personal Information */}
        <div className="rounded-2xl border border-slate-200 bg-white p-8 lg:col-span-2">
          <div className="flex items-start justify-between gap-3">
            <div>
              <h2 className="font-semibold text-slate-900">Personal Information</h2>
              <p className="text-sm text-slate-500">Update your personal details</p>
            </div>
            {isEditing ? (
              <div className="flex shrink-0 gap-2">
                <button
                  onClick={() => setIsEditing(false)}
                  className="rounded-lg border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-50"
                >
                  Cancel
                </button>
                <button
                  onClick={handleSave}
                  className="rounded-lg bg-teal-500 px-4 py-2 text-sm font-semibold text-white transition hover:bg-teal-400"
                >
                  Save
                </button>
              </div>
            ) : (
              <button
                onClick={startEditing}
                className="flex shrink-0 items-center gap-2 rounded-lg border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-50"
              >
                <PencilIcon className="h-4 w-4" />
                Edit
              </button>
            )}
          </div>

          {/* Avatar + name */}
          <div className="mt-6 flex items-center gap-4 border-b border-slate-100 pb-6">
            <div className="flex h-16 w-16 shrink-0 items-center justify-center rounded-full bg-teal-500 text-xl font-semibold text-white">
              {getInitials(user?.fullName)}
            </div>
            <div>
              <h3 className="text-lg font-semibold text-slate-900">
                {user?.fullName || 'Guest'}
              </h3>
              <p className="text-slate-500">Project Manager</p>
              <button className="mt-2 rounded-lg border border-slate-200 px-3 py-1.5 text-sm font-medium text-slate-700 transition hover:bg-slate-50">
                Change Avatar
              </button>
            </div>
          </div>

          {/* Details grid */}
          <div className="mt-6 grid grid-cols-1 gap-x-8 gap-y-5 sm:grid-cols-2">
            <ProfileDetail
              icon={UserIcon}
              label="Full Name"
              isEditing={isEditing}
              name="fullName"
              value={form.fullName}
              display={user?.fullName}
              onChange={handleChange}
            />
            <ProfileDetail icon={MailIcon} label="Email" display={user?.email} />
            <ProfileDetail
              icon={PhoneIcon}
              label="Phone"
              isEditing={isEditing}
              name="phoneNumber"
              value={form.phoneNumber}
              display={user?.phoneNumber}
              onChange={handleChange}
            />
            <ProfileDetail
              icon={MapPinIcon}
              label="Location"
              isEditing={isEditing}
              name="location"
              value={form.location}
              display={user?.location}
              onChange={handleChange}
            />
            <ProfileDetail
              icon={BriefcaseIcon}
              label="Department"
              isEditing={isEditing}
              name="department"
              value={form.department}
              display={user?.department}
              onChange={handleChange}
            />
            <ProfileDetail icon={CalendarIcon} label="Joined" display={formatDate(user?.joinedAt)} />
          </div>

          <button
            onClick={handleLogout}
            className="mt-8 flex items-center gap-2 rounded-lg border border-slate-200 px-4 py-2.5 font-semibold text-slate-700 transition hover:bg-slate-50"
          >
            <LogoutIcon className="h-4 w-4" />
            Log Out
          </button>
        </div>

        {/* Right column: Account Stats + Notifications */}
        <div className="space-y-6">
          <div className="rounded-2xl border border-slate-200 bg-white p-6">
            <h2 className="mb-2 font-semibold text-slate-900">Account Stats</h2>
            <div className="divide-y divide-slate-100">
              {accountStats.map((stat) => (
                <div
                  key={stat.label}
                  className="flex items-center justify-between py-3 first:pt-2 last:pb-0"
                >
                  <span className="text-slate-500">{stat.label}</span>
                  <span className="text-lg font-bold text-slate-900">{stat.value}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white p-6">
            <div className="mb-4 flex items-center gap-2">
              <BellIcon className="h-5 w-5 text-slate-400" />
              <h2 className="font-semibold text-slate-900">Notifications</h2>
            </div>
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <span className="text-slate-700">Email notifications</span>
                <Toggle checked={emailNotifications} onChange={setEmailNotifications} />
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-700">Slack alerts</span>
                <Toggle checked={slackAlerts} onChange={setSlackAlerts} />
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
