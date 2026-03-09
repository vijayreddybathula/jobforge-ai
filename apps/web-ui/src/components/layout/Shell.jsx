import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../../contexts/AuthContext'
import { Zap, FileText, Settings, Briefcase, Mail, ChevronDown, LogOut, User } from 'lucide-react'
import { useState } from 'react'

const navItems = [
  { to: '/resume',       label: 'Resume',      icon: FileText },
  { to: '/preferences',  label: 'Preferences', icon: Settings },
  { to: '/jobs',         label: 'Jobs',        icon: Briefcase },
  { to: '/applications', label: 'Applications', icon: Mail },
]

export default function Shell() {
  const { session, logout } = useAuth()
  const navigate = useNavigate()
  const [dropOpen, setDropOpen] = useState(false)

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <div className="min-h-screen flex flex-col">
      {/* Top nav */}
      <header className="border-b border-surface-border bg-surface-card/80 backdrop-blur sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-6 h-14 flex items-center gap-8">
          {/* Logo */}
          <NavLink to="/dashboard" className="flex items-center gap-2 font-bold text-lg shrink-0">
            <Zap size={20} className="text-brand" />
            <span className="bg-gradient-to-r from-brand to-purple-400 bg-clip-text text-transparent">
              JobForge AI
            </span>
          </NavLink>

          {/* Nav links */}
          <nav className="flex items-center gap-1 flex-1">
            {navItems.map(({ to, label, icon: Icon }) => (
              <NavLink
                key={to}
                to={to}
                className={({ isActive }) =>
                  `flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                    isActive
                      ? 'bg-brand/15 text-brand'
                      : 'text-slate-400 hover:text-slate-200 hover:bg-surface-hover'
                  }`
                }
              >
                <Icon size={15} />
                {label}
              </NavLink>
            ))}
          </nav>

          {/* User menu */}
          <div className="relative">
            <button
              onClick={() => setDropOpen(v => !v)}
              className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm text-slate-300 hover:bg-surface-hover transition-colors"
            >
              <div className="w-6 h-6 rounded-full bg-brand/30 flex items-center justify-center text-brand text-xs font-bold">
                {(session?.full_name || session?.email || 'U')[0].toUpperCase()}
              </div>
              <span className="max-w-[120px] truncate">{session?.full_name || session?.email}</span>
              <ChevronDown size={14} />
            </button>

            {dropOpen && (
              <>
                <div className="fixed inset-0 z-40" onClick={() => setDropOpen(false)} />
                <div className="absolute right-0 top-full mt-1 w-44 bg-surface-card border border-surface-border rounded-xl shadow-xl z-50 overflow-hidden">
                  <div className="px-3 py-2 border-b border-surface-border">
                    <p className="text-xs text-slate-500 truncate">{session?.email}</p>
                  </div>
                  <button
                    onClick={handleLogout}
                    className="w-full flex items-center gap-2 px-3 py-2.5 text-sm text-red-400 hover:bg-red-900/20 transition-colors"
                  >
                    <LogOut size={14} /> Sign out
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      </header>

      {/* Page content */}
      <main className="flex-1 max-w-7xl mx-auto w-full px-6 py-8">
        <Outlet />
      </main>
    </div>
  )
}
