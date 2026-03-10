import { createContext, useContext, useState, useCallback } from 'react'

// NOTE: localStorage stores a non-sensitive session reference (user_id + email).
// No passwords, tokens or PII beyond what is needed for API headers.
// The server is the authoritative source of truth — this is only a UI-side cache.
// For production, consider migrating to httpOnly cookies via a /me endpoint.
const SESSION_KEY = 'jf_session'
const SESSION_TTL_MS = 8 * 60 * 60 * 1000 // 8 hours

const AuthContext = createContext(null)

function readSession() {
  try {
    const raw = localStorage.getItem(SESSION_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw)
    if (Date.now() - new Date(parsed.logged_in_at).getTime() > SESSION_TTL_MS) {
      localStorage.removeItem(SESSION_KEY)
      return null
    }
    return parsed
  } catch {
    return null
  }
}

export function AuthProvider({ children }) {
  const [session, setSession] = useState(() => readSession())

  const login = useCallback((userData) => {
    // Only store non-sensitive identity fields — never store passwords or raw tokens
    const safe = {
      user_id:    userData.user_id,
      email:      userData.email,
      full_name:  userData.full_name,
      logged_in_at: new Date().toISOString(),
    }
    localStorage.setItem(SESSION_KEY, JSON.stringify(safe))
    setSession(safe)
  }, [])

  const logout = useCallback(() => {
    localStorage.removeItem(SESSION_KEY)
    setSession(null)
  }, [])

  return (
    <AuthContext.Provider value={{ session, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
