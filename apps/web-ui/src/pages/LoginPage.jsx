import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { Zap, Eye, EyeOff } from 'lucide-react'
import Spinner from '../components/common/Spinner'

export default function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPass, setShowPass] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async () => {
    if (!email || !password) { setError('Email and password are required.'); return }
    setError('')
    setLoading(true)
    try {
      const res = await fetch('/api/v1/users/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      })
      const data = await res.json()
      if (!res.ok) { setError(data.detail || 'Login failed.'); return }
      login(data)
      navigate('/dashboard')
    } catch {
      setError('Network error. Is the API running?')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-surface flex items-center justify-center px-4">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center gap-2 mb-3">
            <Zap size={28} className="text-brand" />
            <span className="text-2xl font-bold bg-gradient-to-r from-brand to-purple-400 bg-clip-text text-transparent">
              JobForge AI
            </span>
          </div>
          <p className="text-slate-400 text-sm">Intelligent Job Application Agent</p>
        </div>

        {/* Card */}
        <div className="card">
          <h2 className="text-lg font-semibold text-slate-200 mb-6">Sign in to continue</h2>

          <div className="space-y-4">
            <div>
              <label className="label">Email</label>
              <input
                type="email"
                className="input"
                placeholder="you@example.com"
                value={email}
                onChange={e => setEmail(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleSubmit()}
                autoFocus
              />
            </div>

            <div>
              <label className="label">Password</label>
              <div className="relative">
                <input
                  type={showPass ? 'text' : 'password'}
                  className="input pr-10"
                  placeholder="••••••••"
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && handleSubmit()}
                />
                <button
                  type="button"
                  onClick={() => setShowPass(v => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300"
                >
                  {showPass ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            {error && (
              <div className="bg-red-950 border border-red-500/30 text-red-400 text-sm px-3 py-2 rounded-lg">
                {error}
              </div>
            )}

            <button
              onClick={handleSubmit}
              disabled={loading}
              className="btn-primary w-full flex items-center justify-center gap-2 py-2.5"
            >
              {loading ? <><Spinner size="sm" /> Signing in...</> : 'Sign In'}
            </button>
          </div>

          <p className="mt-5 text-center text-sm text-slate-500">
            Don't have an account?{' '}
            <Link to="/signup" className="text-brand hover:text-brand-hover font-medium">Sign up →</Link>
          </p>
        </div>
      </div>
    </div>
  )
}
