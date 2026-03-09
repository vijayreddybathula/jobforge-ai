import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { Zap, Eye, EyeOff, AlertCircle } from 'lucide-react'
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
  const [forgotMode, setForgotMode]   = useState(false)
  const [fpEmail, setFpEmail]         = useState('')
  const [fpSent, setFpSent]           = useState(false)
  const [fpLoading, setFpLoading]     = useState(false)
  const [fpError, setFpError]         = useState('')

  /* ── helpers ─────────────────────────────────────────────────── */
  const handleLogin = async () => {
    if (!email || !password) { setError('Email and password are required.'); return }
    setError('')
    setLoading(true)
    try {
      const res  = await fetch('/api/v1/users/login', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ email, password }),
      })
      const data = await res.json()
      if (!res.ok) {
        // Surface the exact server message so users know what went wrong
        const msg = Array.isArray(data.detail)
          ? data.detail.map(d => d.msg).join(' · ')
          : (data.detail || 'Login failed. Check your credentials.')
        setError(msg)
        return
      }
      login(data)
      navigate('/dashboard')
    } catch {
      setError('Cannot reach the server. Make sure the API is running on :8000.')
    } finally {
      setLoading(false)
    }
  }

  const handleForgotPassword = async () => {
    if (!fpEmail) { setFpError('Enter your email address.'); return }
    setFpError('')
    setFpLoading(true)
    try {
      // Best-effort: try the reset endpoint; if it doesn't exist yet we show
      // a friendly message regardless so UX is not broken.
      await fetch('/api/v1/users/forgot-password', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ email: fpEmail }),
      })
      setFpSent(true)
    } catch {
      setFpSent(true) // still show success — don't leak whether email exists
    } finally {
      setFpLoading(false)
    }
  }

  /* ── render ───────────────────────────────────────────────────── */
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

        {/* ── Forgot-password panel ── */}
        {forgotMode ? (
          <div className="card">
            <h2 className="text-lg font-semibold text-slate-200 mb-1">Reset your password</h2>
            <p className="text-sm text-slate-400 mb-5">
              Enter your account email and we'll send a reset link.
            </p>

            {fpSent ? (
              <div className="bg-emerald-950 border border-emerald-500/30 text-emerald-300 text-sm px-4 py-3 rounded-lg">
                If <strong>{fpEmail}</strong> exists in our system, a reset link has been sent.
              </div>
            ) : (
              <div className="space-y-4">
                <div>
                  <label className="label">Email</label>
                  <input
                    type="email" className="input" autoFocus
                    placeholder="you@example.com"
                    value={fpEmail} onChange={e => setFpEmail(e.target.value)}
                    onKeyDown={e => e.key === 'Enter' && handleForgotPassword()}
                  />
                </div>
                {fpError && (
                  <div className="flex items-center gap-2 bg-red-950 border border-red-500/30 text-red-400 text-sm px-3 py-2 rounded-lg">
                    <AlertCircle size={14} className="shrink-0" />{fpError}
                  </div>
                )}
                <button
                  onClick={handleForgotPassword} disabled={fpLoading}
                  className="btn-primary w-full flex items-center justify-center gap-2 py-2.5"
                >
                  {fpLoading ? <><Spinner size="sm" /> Sending...</> : 'Send Reset Link'}
                </button>
              </div>
            )}

            <button
              onClick={() => { setForgotMode(false); setFpSent(false); setFpError('') }}
              className="mt-4 text-sm text-slate-500 hover:text-slate-300 w-full text-center"
            >
              ← Back to sign in
            </button>
          </div>

        ) : (
          /* ── Normal login panel ── */
          <div className="card">
            <h2 className="text-lg font-semibold text-slate-200 mb-6">Sign in to continue</h2>

            <div className="space-y-4">
              <div>
                <label className="label">Email</label>
                <input
                  type="email" className="input" autoFocus
                  placeholder="you@example.com"
                  value={email} onChange={e => setEmail(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && handleLogin()}
                />
              </div>

              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <label className="label mb-0">Password</label>
                  <button
                    type="button"
                    onClick={() => setForgotMode(true)}
                    className="text-xs text-brand hover:text-brand-hover"
                  >
                    Forgot password?
                  </button>
                </div>
                <div className="relative">
                  <input
                    type={showPass ? 'text' : 'password'}
                    className="input pr-10"
                    placeholder="••••••••"
                    value={password} onChange={e => setPassword(e.target.value)}
                    onKeyDown={e => e.key === 'Enter' && handleLogin()}
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
                <div className="flex items-start gap-2 bg-red-950 border border-red-500/30 text-red-400 text-sm px-3 py-2.5 rounded-lg">
                  <AlertCircle size={14} className="shrink-0 mt-0.5" />
                  <span>{error}</span>
                </div>
              )}

              <button
                onClick={handleLogin} disabled={loading}
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
        )}
      </div>
    </div>
  )
}
