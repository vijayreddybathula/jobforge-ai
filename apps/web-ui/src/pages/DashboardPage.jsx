import { useEffect, useState, useRef } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { useApi } from '../hooks/useApi'
import { CheckCircle, Circle, ArrowRight, FileText, Briefcase, Star, Send } from 'lucide-react'
import Spinner from '../components/common/Spinner'

function CheckItem({ done, label, to }) {
  return (
    <div className="flex items-center gap-3 py-2">
      {done
        ? <CheckCircle size={18} className="text-emerald-400 shrink-0" />
        : <Circle     size={18} className="text-slate-600 shrink-0" />}
      <span className={`text-sm ${done ? 'text-slate-300' : 'text-slate-500'}`}>{label}</span>
      {!done && to && (
        <Link to={to} className="ml-auto text-brand text-xs flex items-center gap-1 hover:underline">
          Get started <ArrowRight size={12} />
        </Link>
      )}
    </div>
  )
}

export default function DashboardPage() {
  const { session } = useAuth()
  const api         = useApi()

  const [status,       setStatus]       = useState({ loading: true, resume: false, roles: false, prefs: false })
  const [recentScores, setRecentScores] = useState([])

  // Guard so we only fire the load once per mount, even in React Strict Mode
  const didLoad = useRef(false)

  const firstName = session?.full_name?.split(' ')[0] || 'there'
  const hour      = new Date().getHours()
  const greeting  = hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening'

  useEffect(() => {
    if (didLoad.current) return
    didLoad.current = true

    async function load() {
      const s = { loading: false, resume: false, roles: false, prefs: false }

      // 1. Resumes
      try {
        const resumes = await api.get('/resume/')
        s.resume = Array.isArray(resumes) && resumes.length > 0
        if (s.resume) {
          // Only check the first / most recent resume to avoid N requests
          const firstId = resumes[0].resume_id
          const rolesData = await api.get(`/resume/roles/${firstId}`)
          s.roles = rolesData.roles?.some(r => r.is_confirmed) ?? false
        }
      } catch {}

      // 2. Preferences
      try {
        await api.get('/preferences/')
        s.prefs = true
      } catch {}

      // 3. Recent scored jobs (single request)
      try {
        const jobs   = await api.get('/jobs/?page=1&limit=10')
        const scored = (jobs.jobs || []).filter(j => j.score !== null)
        setRecentScores(scored.slice(0, 5))
      } catch {}

      setStatus(s)
    }

    load()
  }, []) // empty deps — api is stable, runs once on mount

  const statCards = [
    {
      label: 'Resume',
      value: status.resume ? '✓' : '—',
      sub:   status.resume ? 'Uploaded' : 'Not uploaded',
      icon:  FileText,
      color: status.resume ? 'text-emerald-400' : 'text-slate-500',
    },
    {
      label: 'Jobs',
      value: recentScores.length || '—',
      sub:   'recently scored',
      icon:  Briefcase,
      color: 'text-brand',
    },
    {
      label: 'To Apply',
      value: recentScores.filter(j => j.verdict === 'ASSISTED_APPLY').length || '—',
      sub:   'APPLY verdict',
      icon:  Send,
      color: 'text-emerald-400',
    },
    {
      label: 'Avg Score',
      value: recentScores.length
        ? Math.round(recentScores.reduce((a, j) => a + j.score, 0) / recentScores.length)
        : '—',
      sub:   'across scored',
      icon:  Star,
      color: 'text-amber-400',
    },
  ]

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-slate-100">{greeting}, {firstName} 👋</h1>
        <p className="text-slate-400 mt-1 text-sm">Here's your pipeline status</p>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {statCards.map(({ label, value, sub, icon: Icon, color }) => (
          <div key={label} className="card">
            <div className="flex items-start justify-between mb-3">
              <span className="text-xs text-slate-500 uppercase tracking-wider">{label}</span>
              <Icon size={16} className={color} />
            </div>
            <div className={`text-3xl font-bold mb-1 ${color}`}>
              {status.loading ? <Spinner size="sm" /> : value}
            </div>
            <div className="text-xs text-slate-500">{sub}</div>
          </div>
        ))}
      </div>

      <div className="grid md:grid-cols-2 gap-6">
        {/* Checklist */}
        <div className="card">
          <h2 className="font-semibold text-slate-200 mb-4">Onboarding Checklist</h2>
          <div className="divide-y divide-surface-border">
            <CheckItem done={status.resume} label="Upload your resume"       to="/resume" />
            <CheckItem done={status.roles}  label="Confirm target roles"     to={status.resume ? `/resume` : '/resume'} />
            <CheckItem done={status.prefs}  label="Set job preferences"      to="/preferences" />
            <CheckItem done={recentScores.length > 0} label="Search & score jobs" to="/jobs" />
            <CheckItem
              done={recentScores.some(j => j.verdict === 'ASSISTED_APPLY')}
              label="Generate artifacts & apply"
              to="/jobs"
            />
          </div>
        </div>

        {/* Recent scored jobs */}
        <div className="card">
          <h2 className="font-semibold text-slate-200 mb-4">Recent Scored Jobs</h2>
          {status.loading ? (
            <div className="flex justify-center py-8"><Spinner /></div>
          ) : recentScores.length === 0 ? (
            <p className="text-sm text-slate-500 py-4">
              No scored jobs yet.{' '}
              <Link to="/jobs" className="text-brand hover:underline">Go to Jobs →</Link>
            </p>
          ) : (
            <div className="space-y-2">
              {recentScores.map(j => (
                <Link
                  key={j.job_id}
                  to={`/jobs/${j.job_id}`}
                  className="flex items-center gap-3 p-2 rounded-lg hover:bg-surface-hover transition-colors"
                >
                  <div className={`w-9 h-9 rounded-full flex items-center justify-center text-sm font-bold border ${
                    j.score >= 85 ? 'text-brand border-brand/40 bg-brand/10'
                    : j.score >= 75 ? 'text-emerald-400 border-emerald-500/40 bg-emerald-900/20'
                    : 'text-amber-400 border-amber-500/40 bg-amber-900/20'
                  }`}>{j.score}</div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-slate-200 truncate">
                      {j.parsed_role || j.title || 'Unknown Role'}
                    </p>
                    <p className="text-xs text-slate-500 truncate">{j.company}</p>
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
