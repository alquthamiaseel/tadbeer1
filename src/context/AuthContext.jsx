import { createContext, useContext, useEffect, useState } from 'react'

// ---------------------------------------------------------------------------
// AuthContext
// ---------------------------------------------------------------------------
// This app has no real backend yet, so "authentication" here just means:
// "do we have a user's name/email stored so we can greet them and show a
// profile page?". When a real backend is added later, only the login()
// and register() functions below need to change - every page that uses
// this context (Dashboard, Sidebar, Profile, etc.) can stay the same.
//
// We save the current user to localStorage so a page refresh doesn't log
// the user out immediately - this keeps the demo usable.
// ---------------------------------------------------------------------------

const AuthContext = createContext(null)

const STORAGE_KEY = 'tadbeer_current_user'

export function AuthProvider({ children }) {
  // Try to load a previously saved user when the app first starts.
  const [user, setUser] = useState(() => {
    const saved = localStorage.getItem(STORAGE_KEY)
    return saved ? JSON.parse(saved) : null
  })

  // Whenever `user` changes, keep localStorage in sync.
  useEffect(() => {
    if (user) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(user))
    } else {
      localStorage.removeItem(STORAGE_KEY)
    }
  }, [user])

  // Called by the Login page. In a real app this would call an API and
  // check the password - for now we just "log in" with whatever was typed.
  function login({ email }) {
    setUser({ fullName: email.split('@')[0], email, joinedAt: new Date().toISOString() })
  }

  // Called by the Register page once the sign-up form is submitted.
  function register(userDetails) {
    setUser({ ...userDetails, joinedAt: new Date().toISOString() })
  }

  // Called from the Sidebar/Profile page to sign the user out.
  function logout() {
    setUser(null)
  }

  const value = { user, login, register, logout, setUser }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

// Small helper hook so components can just do `const { user } = useAuth()`
// instead of importing useContext + AuthContext everywhere.
export function useAuth() {
  return useContext(AuthContext)
}
