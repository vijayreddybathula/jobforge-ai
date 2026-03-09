import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { Zap, Eye, EyeOff } from 'lucide-react'
import Spinner from '../components/common/Spinner'

export default function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail]       = useState('')
  const [password, setPassword] = useState('')
  const [showPass, setShowPass] = useState(false)
  const [error, setError]       = useState('')
  const [loading, setLoading]   = useState(false)

  // Forgot-password flow
  const [forgotMode, setForgotMode]     = useState(false)
  const [resetEmail, setResetEmail]     = useState('')
  const [resetSent, setResetSent]       = useState(false)
  const [resetLoading, setResetLoading] = useState(false)
  const [resetError, setResetError]     = useState('')

  /* ── Login ─────────────────────────────────────────────────── */
  const handleSubmit = async () => {
    if (!email || !password) { setError('Email and password are required.'); return }
    setError('')
    setLoading(true)
    try {
      const res  = await fetch('/api/v1/users/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      })
      const data = await res.json()

      if (!res.ok) {
        const msg = typeof data.detail === 'string'
          ? data.detail
          : Array.isArray(data.detail)
            ? data.detail.map(d => d.msg).join(', ')
            : 'Login failed. Please check your credentials.'
        setError(msg)
        return
      }

      login(data)
      navigate('/dashboard')
    } catch {
      setError('Network error — is the API running on port 8000?')
    } finally {
      setLoading(false)
    }
  }

  /* ── Forgot password ────────────────────────────────────────── */
  const handleForgotPassword = async () => {
    if (!resetEmail) { setResetError('Enter your email address.'); return }
    setResetError('')
    setResetLoading(true)
    try {
      const res = await fetch('/api/v1/users/forgot-password', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: resetEmail }),
      })
      // Security best-practice: always show success regardless of whether email exists.
      // But surface real network/server errors (5xx) to the user.
      if (res.status >= 500) {
        setResetError('Server error — please try again later.')
        return
      }
      setResetSent(true)
    } catch {
      setResetError('Network error — try again.')
    } finally {
      setResetLoading(false)
    }
  }

  /* ── Forgot-password panel ─────────────────────────────────── */
  if (forgotMode) {
    return (
      <div className="min-h-screen bg-surface flex items-center justify-center px-4">
        <div className="w-full max-w-md">
          <div className="text-center mb-8">
            <div className="inline-flex items-center gap-2 mb-3">
              <Zap size={28} className="text-brand" />
              <span className="text-2xl font-bold bg-gradient-to-r from-brand to-purple-400 bg-clip-text text-transparent">JobForge AI</span>
            </div>
          </div>

          <div className="card">
            {resetSent ? (
              <div className="text-center py-4">
                <div className="w-12 h-12 bg-emerald-900/30 border border-emerald-500/30 rounded-full flex items-center justify-center mx-auto mb-4">
                  <span className="text-2xl">✓</span>
                </div>
                <h2 className="text-lg font-semibold text-slate-200 mb-2">Check your email</h2>
                <p className="text-sm text-slate-400 mb-6">
                  If an account exists for <strong className="text-slate-300">{resetEmail}</strong>,
                  you'll receive reset instructions shortly.
                </p>
                <button onClick={() => { setForgotMode(false); setResetSent(false) }} className="btn-primary w-full">
                  Back to Sign In
                </button>
              </div>
            ) : (
              <>
                <h2 className="text-lg font-semibold text-slate-200 mb-1">Reset your password</h2>
                <p className="text-sm text-slate-400 mb-6">Enter your email and we'll send reset instructions.</p>

                <div className="space-y-4">
                  <div>
                    <label className="label">Email</label>
                    <input
                      type="email" className="input" placeholder="you@example.com"
                      value={resetEmail} onChange={e => setResetEmail(e.target.value)}
                      onKeyDown={e => e.key === 'Enter' && handleForgotPassword()}
                      autoFocus
                    />
                  </div>

                  {resetError && (
                    <div className="bg-red-950 border border-red-500/30 text-red-400 text-sm px-3 py-2 rounded-lg">{resetError}</div>
                  )}

                  <button onClick={handleForgotPassword} disabled={resetLoading} className="btn-primary w-full flex items-center justify-center gap-2 py-2.5">
                    {resetLoading ? <><Spinner size="sm" /> Sending...</> : 'Send Reset Link'}
                  </button>

                  <button onClick={() => setForgotMode(false)} className="w-full text-sm text-slate-500 hover:text-slate-300 text-center py-1">
                    ← Back to sign in
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    )
  }

  /* ── Normal login panel ────────────────────────────────────── */
  return (
    <div className="min-h-screen bg-surface flex items-center justify-center px-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="inline-flex items-center gap-2 mb-3">
            <Zap size={28} className="text-brand" />
            <span className="text-2xl font-bold bg-gradient-to-r from-brand to-purple-400 bg-clip-text text-transparent">JobForge AI</span>
          </div>
          <p className="text-slate-400 text-sm">Intelligent Job Application Agent</p>
        </div>

        <div className="card">
          <h2 className="text-lg font-semibold text-slate-200 mb-6">Sign in to continue</h2>

          <div className="space-y-4">
            <div>
              <label className="label">Email</label>
              <input
                type="email" className="input" placeholder="you@example.com"
                value={email} onChange={e => setEmail(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleSubmit()}
                autoFocus
              />
            </div>

            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="label mb-0">Password</label>
                <button
                  type="button"
                  onClick={() => { setForgotMode(true); setResetEmail(email) }}
                  className="text-xs text-brand hover:text-brand-hover"
                >
                  Forgot password?
                </button>
              </div>
              <div className="relative">
                <input
                  type={showPass ? 'text' : 'password'} className="input pr-10"
                  placeholder="••••••••"
                  value={password} onChange={e => setPassword(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && handleSubmit()}
                />
                <button type="button" onClick={() => setShowPass(v => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300">
                  {showPass ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            {error && (
              <div className="bg-red-950 border border-red-500/30 text-red-400 text-sm px-3 py-2.5 rounded-lg leading-relaxed">
                {error}
              </div>
            )}

            <button onClick={handleSubmit} disabled={loading}
              className="btn-primary w-full flex items-center justify-center gap-2 py-2.5">
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
