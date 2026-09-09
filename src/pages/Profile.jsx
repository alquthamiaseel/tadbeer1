import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext.jsx'
import { UserIcon, MailIcon, PhoneIcon, MapPinIcon, BriefcaseIcon, LogoutIcon } from '../components/icons.jsx'

// One row in the profile details list: an icon, a label, and the value.
// Falls back to "Not provided" so the layout doesn't break when a field
// was never filled in (e.g. a user who signed in instead of registering).
function ProfileField({ icon: Icon, label, value }) {
  return (
    <div className="flex items-center gap-4 border-b border-slate-100 py-4 last:border-b-0">
      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-teal-50 text-teal-600">
        <Icon className="h-5 w-5" />
      </div>
      <div>
        <p className="text-sm text-slate-500">{label}</p>
        <p className="font-medium text-slate-900">{value || 'Not provided'}</p>
      </div>
    </div>
  )
}

export default function Profile() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  function handleLogout() {
    logout()
    navigate('/login')
  }

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

  return (
    <div>
      <h1 className="text-3xl font-bold text-slate-900">Profile</h1>
      <p className="mt-1 text-slate-500">Your account information</p>

      <div className="mt-6 max-w-xl rounded-2xl border border-slate-200 bg-white p-8">
        {/* Avatar + name header */}
        <div className="flex items-center gap-4">
          <div className="flex h-16 w-16 items-center justify-center rounded-full bg-teal-500 text-xl font-semibold text-white">
            {getInitials(user?.fullName)}
          </div>
          <div>
            <h2 className="text-xl font-semibold text-slate-900">
              {user?.fullName || 'Guest'}
            </h2>
            <p className="text-slate-500">Project Manager</p>
          </div>
        </div>

        {/* Account details list */}
        <div className="mt-6">
          <ProfileField icon={UserIcon} label="Full Name" value={user?.fullName} />
          <ProfileField icon={MailIcon} label="Email Address" value={user?.email} />
          <ProfileField icon={PhoneIcon} label="Phone Number" value={user?.phoneNumber} />
          <ProfileField icon={MapPinIcon} label="Location" value={user?.location} />
          <ProfileField icon={BriefcaseIcon} label="Department" value={user?.department} />
        </div>

        <button
          onClick={handleLogout}
          className="mt-6 flex items-center gap-2 rounded-lg border border-slate-200 px-4 py-2.5 font-semibold text-slate-700 transition hover:bg-slate-50"
        >
          <LogoutIcon className="h-4 w-4" />
          Log Out
        </button>
      </div>
    </div>
  )
}
