import { createContext, useContext, useState, useEffect, useCallback } from 'react'

const SESSION_KEY = 'jf_session'
const SESSION_TTL_MS = 8 * 60 * 60 * 1000 // 8 hours

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [session, setSession] = useState(() => {
    try {
      const raw = localStorage.getItem(SESSION_KEY)
      if (!raw) return null
      const parsed = JSON.parse(raw)
      // Expire after 8h
      if (Date.now() - new Date(parsed.logged_in_at).getTime() > SESSION_TTL_MS) {
        localStorage.removeItem(SESSION_KEY)
        return null
      }
      return parsed
    } catch {
      return null
    }
  })

  const login = useCallback((userData) => {
    const s = { ...userData, logged_in_at: new Date().toISOString() }
    localStorage.setItem(SESSION_KEY, JSON.stringify(s))
    setSession(s)
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
