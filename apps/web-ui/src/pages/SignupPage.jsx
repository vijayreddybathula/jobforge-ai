import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { Zap } from 'lucide-react'
import Spinner from '../components/common/Spinner'

export default function SignupPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [form, setForm] = useState({ full_name: '', email: '', password: '' })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const set = (k) => (e) => setForm(f => ({ ...f, [k]: e.target.value }))

  const handleSubmit = async () => {
    if (!form.full_name || !form.email || !form.password) {
      setError('All fields are required.'); return
    }
    if (form.password.length < 8) {
      setError('Password must be at least 8 characters.'); return
    }
    setError('')
    setLoading(true)
    try {
      const res = await fetch('/api/v1/users/signup', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      })
      const data = await res.json()
      if (!res.ok) { setError(data.detail || 'Signup failed.'); return }
      login(data)
      navigate('/resume') // Onboarding: start with resume upload
    } catch {
      setError('Network error. Is the API running?')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-surface flex items-center justify-center px-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="inline-flex items-center gap-2 mb-3">
            <Zap size={28} className="text-brand" />
            <span className="text-2xl font-bold bg-gradient-to-r from-brand to-purple-400 bg-clip-text text-transparent">
              JobForge AI
            </span>
          </div>
          <p className="text-slate-400 text-sm">Your personal AI job application agent</p>
        </div>

        <div className="card">
          <h2 className="text-lg font-semibold text-slate-200 mb-6">Create your account</h2>

          <div className="space-y-4">
            <div>
              <label className="label">Full Name</label>
              <input type="text" className="input" placeholder="Vijay Reddybathula" value={form.full_name} onChange={set('full_name')} autoFocus />
            </div>
            <div>
              <label className="label">Email</label>
              <input type="email" className="input" placeholder="you@example.com" value={form.email} onChange={set('email')} />
            </div>
            <div>
              <label className="label">Password</label>
              <input type="password" className="input" placeholder="Min. 8 characters" value={form.password} onChange={set('password')} onKeyDown={e => e.key === 'Enter' && handleSubmit()} />
            </div>

            {error && (
              <div className="bg-red-950 border border-red-500/30 text-red-400 text-sm px-3 py-2 rounded-lg">{error}</div>
            )}

            <button onClick={handleSubmit} disabled={loading} className="btn-primary w-full flex items-center justify-center gap-2 py-2.5">
              {loading ? <><Spinner size="sm" /> Creating account...</> : 'Create Account'}
            </button>
          </div>

          <p className="mt-5 text-center text-sm text-slate-500">
            Already have an account?{' '}
            <Link to="/login" className="text-brand hover:text-brand-hover font-medium">Sign in →</Link>
          </p>
        </div>
      </div>
    </div>
  )
}
