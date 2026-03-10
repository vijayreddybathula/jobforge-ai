import { useEffect, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useApi } from '../hooks/useApi'
import { Search, Zap, Briefcase, ChevronRight } from 'lucide-react'
import VerdictBadge from '../components/jobs/VerdictBadge'
import ScoreCircle from '../components/jobs/ScoreCircle'
import Spinner from '../components/common/Spinner'
import Toast from '../components/common/Toast'
import EmptyState from '../components/common/EmptyState'

/**
 * JSearch date_posted options.
 * Note: JSearch does NOT support a 1-hour window — "today" is the finest
 * granularity available and covers roughly the last 24 hours.
 */
const DATE_POSTED_OPTIONS = [
  { value: 'today',  label: 'Last 24 hours' },
  { value: '3days',  label: 'Last 3 days'   },
  { value: 'week',   label: 'Last 7 days'   },
  { value: 'month',  label: 'Last 30 days'  },
  { value: 'any',    label: 'Any time'      },
]

function deriveWorkType(locPrefs) {
  if (!locPrefs) return 'remote,hybrid'
  const types = []
  if (locPrefs.remote) types.push('remote')
  if (locPrefs.hybrid) types.push('hybrid')
  if (locPrefs.onsite) types.push('onsite')
  return types.length ? types.join(',') : 'remote,hybrid'
}

/**
 * Pick the best keyword from the user's confirmed roles.
 *
 * Strategy:
 *   1. Call /resume/roles/{resumeId} to get confidence_score per role.
 *   2. Return the role_title with the highest confidence_score.
 *   3. If that endpoint fails or returns nothing, fall back to core_roles[0].
 *
 * This fixes the bug where core_roles[0] was always used (alphabetical order),
 * so "AI Solutions Architect" filled in instead of "Senior GenAI Engineer".
 */
async function pickBestKeyword(api) {
  try {
    // Get profile to find the resume_id
    const profile = await api.get('/profile')
    const resumes = await api.get('/resume/')
    const resumeId = resumes?.[0]?.resume_id

    if (resumeId) {
      const rolesResp = await api.get(`/resume/roles/${resumeId}`)
      const roles = rolesResp?.roles || []
      if (roles.length > 0) {
        // Sort by confidence_score descending, pick the top confirmed role first
        const confirmed = roles.filter(r => r.is_confirmed)
        const pool      = confirmed.length > 0 ? confirmed : roles
        const best      = pool.sort((a, b) => (b.confidence_score ?? 0) - (a.confidence_score ?? 0))[0]
        if (best?.role_title) return best.role_title
      }
    }

    // Fallback: use first core_role from profile
    return profile?.core_roles?.[0] || ''
  } catch (_) {
    return ''
  }
}

/* ── Search modal ────────────────────────────────────────────── */
function SearchModal({ onClose, onSuccess, api }) {
  const [form, setForm] = useState({
    keywords:    '',
    location:    '',
    work_type:   'remote,hybrid',
    date_posted: 'week',
    max_results: 10,
  })
  const [loading,     setLoading]     = useState(false)
  const [prefLoading, setPrefLoading] = useState(true)
  const [result,      setResult]      = useState(null)
  const set = k => e => setForm(f => ({ ...f, [k]: e.target.value }))

  useEffect(() => {
    let cancelled = false
    async function loadDefaults() {
      try {
        const [bestKeyword, prefsResult] = await Promise.allSettled([
          pickBestKeyword(api),
          api.get('/preferences/'),
        ])
        if (cancelled) return
        setForm(prev => {
          const next = { ...prev }

          // Best keyword: highest-confidence confirmed role
          if (bestKeyword.status === 'fulfilled' && bestKeyword.value) {
            next.keywords = bestKeyword.value
          }

          // Location + work type from preferences
          if (prefsResult.status === 'fulfilled' && prefsResult.value) {
            const locPrefs = prefsResult.value.location_preferences || {}
            const cities   = locPrefs.cities || []
            next.location  = cities.length ? cities[0] : 'United States'
            next.work_type = deriveWorkType(locPrefs)
          }
          return next
        })
      } catch (_) {
        // non-fatal
      } finally {
        if (!cancelled) setPrefLoading(false)
      }
    }
    loadDefaults()
    return () => { cancelled = true }
  }, [api])

  const search = async () => {
    setLoading(true)
    setResult(null)
    try {
      const params = new URLSearchParams({
        keywords:    form.keywords,
        location:    form.location,
        work_type:   form.work_type,
        date_posted: form.date_posted,
        max_results: form.max_results,
        auto_parse:  true,
      })
      const data = await api.post(`/jobs/search?${params}`)
      setResult(data)
      if (!data.error) onSuccess()
    } catch (e) {
      setResult({ error: e.message })
    } finally { setLoading(false) }
  }

  return (
    <div
      className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4"
      onClick={e => e.target === e.currentTarget && onClose()}
    >
      <div className="bg-surface-card border border-surface-border rounded-2xl w-full max-w-md p-6">
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-lg font-semibold">Search Jobs via JSearch</h2>
          <button onClick={onClose} className="text-slate-500 hover:text-slate-300 text-xl leading-none">×</button>
        </div>

        {prefLoading ? (
          <div className="flex justify-center py-8"><Spinner size="md" /></div>
        ) : (
          <div className="space-y-4">
            <div>
              <label className="label">Keywords</label>
              <input className="input" value={form.keywords} onChange={set('keywords')}
                placeholder="e.g. Senior GenAI Engineer" />
              <p className="text-xs text-slate-500 mt-1">Best-match confirmed role — edit freely</p>
            </div>

            <div>
              <label className="label">Location</label>
              <input className="input" value={form.location} onChange={set('location')}
                placeholder="e.g. Dallas, TX" />
              <p className="text-xs text-slate-500 mt-1">From your location preferences — edit freely</p>
            </div>

            {/* Two-column row: Work Type + Posted Within */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="label">Work Type</label>
                <select className="input" value={form.work_type} onChange={set('work_type')}>
                  <option value="remote,hybrid">Remote + Hybrid</option>
                  <option value="remote">Remote only</option>
                  <option value="hybrid">Hybrid only</option>
                  <option value="onsite">Onsite</option>
                  <option value="remote,hybrid,onsite">Any</option>
                </select>
              </div>

              <div>
                <label className="label">Posted Within</label>
                <select className="input" value={form.date_posted} onChange={set('date_posted')}>
                  {DATE_POSTED_OPTIONS.map(o => (
                    <option key={o.value} value={o.value}>{o.label}</option>
                  ))}
                </select>
              </div>
            </div>
            <p className="text-xs text-slate-600 -mt-2">
              "Last 24 hours" is the finest window JSearch supports.
            </p>

            <div>
              <label className="label">Max Results</label>
              <select className="input" value={form.max_results} onChange={set('max_results')}>
                {[5, 10, 20, 50].map(n => <option key={n} value={n}>{n} jobs</option>)}
              </select>
            </div>

            {result && (
              <div className={`text-sm px-3 py-2 rounded-lg ${
                result.error
                  ? 'bg-red-950 border border-red-500/30 text-red-400'
                  : 'bg-emerald-950 border border-emerald-500/30 text-emerald-300'
              }`}>
                {result.error
                  ? `Error: ${result.error}`
                  : `✓ Fetched ${result.total_fetched ?? 0} · Ingested ${result.ingested ?? 0} · Dupes ${result.duplicates ?? 0} · Parsed ${result.parsed ?? 0}`
                }
              </div>
            )}

            <button onClick={search} disabled={loading || !form.keywords}
              className="btn-primary w-full flex items-center justify-center gap-2 py-2.5">
              {loading ? <><Spinner size="sm" /> Searching…</> : <><Search size={15} /> Search & Ingest</>}
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

/* ── Jobs page ───────────────────────────────────────────────── */
export default function JobsPage() {
  const api      = useApi()
  const navigate = useNavigate()

  const [jobs,       setJobs]       = useState([])
  const [loading,    setLoading]    = useState(true)
  const [scoring,    setScoring]    = useState(false)
  const [scoringId,  setScoringId]  = useState(null)
  const [filter,     setFilter]     = useState('all')
  const [search,     setSearch]     = useState('')
  const [showSearch, setShowSearch] = useState(false)
  const [toast,      setToast]      = useState(null)
  const [total,      setTotal]      = useState(0)
  const [apiError,   setApiError]   = useState('')

  const loadJobs = useCallback(async () => {
    setLoading(true)
    setApiError('')
    try {
      // Pass verdict filter to backend so total reflects filtered count
      const params = filter !== 'all' ? `?verdict=${filter}&limit=50` : '?page=1&limit=50'
      const data = await api.get(`/jobs/${params}`)
      setJobs(data.jobs || [])
      setTotal(data.total || 0)
    } catch (e) {
      setApiError(e.message)
    } finally { setLoading(false) }
  }, [api, filter])

  useEffect(() => { loadJobs() }, [loadJobs])

  const handleScoreOne = async (jobId) => {
    setScoringId(jobId)
    try {
      const s = await api.post(`/jobs/${jobId}/score`)
      setJobs(prev => prev.map(j =>
        j.job_id === jobId
          ? { ...j, score: s.total_score, verdict: s.verdict, breakdown: s.breakdown, rationale: s.rationale }
          : j
      ))
      setToast({ message: `Scored: ${s.total_score}/100 — ${s.verdict}` })
    } catch (e) {
      setToast({ message: e.message, type: 'error' })
    } finally { setScoringId(null) }
  }

  const handleScoreAll = async () => {
    setScoring(true)
    try {
      const r = await api.post('/jobs/score-all')
      const newlyScored   = r.scored                 ?? r.new_scored     ?? 0
      const alreadyScored = r.skipped_already_scored ?? r.already_scored ?? r.skipped ?? 0
      setToast({ message: `Scored ${newlyScored} new jobs. Skipped ${alreadyScored} already scored.` })
      await loadJobs()
    } catch (e) {
      setToast({ message: e.message, type: 'error' })
    } finally { setScoring(false) }
  }

  const FILTERS = [
    { id: 'all',                  label: 'All' },
    { id: 'NOT_SCORED',           label: 'Unscored' },
    { id: 'ASSISTED_APPLY',       label: 'Apply' },
    { id: 'ELIGIBLE_AUTO_SUBMIT', label: 'Auto' },
    { id: 'VALIDATE',             label: 'Validate' },
    { id: 'SKIP',                 label: 'Skip' },
  ]

  // Client-side title search filter (verdict is now server-side)
  const filtered = search
    ? jobs.filter(j => {
        const q = search.toLowerCase()
        return `${j.title || ''} ${j.company || ''} ${j.parsed_role || ''}`.toLowerCase().includes(q)
      })
    : jobs

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-100">Job Pipeline</h1>
          <p className="text-slate-400 text-sm mt-1">{total} jobs{filter !== 'all' ? ` matching “${filter}”` : ' in catalog'}</p>
        </div>
        <div className="flex gap-2">
          <button onClick={handleScoreAll} disabled={scoring}
            className="btn-secondary flex items-center gap-2">
            {scoring ? <><Spinner size="sm" /> Scoring…</> : <><Zap size={15} /> Score All</>}
          </button>
          <button onClick={() => setShowSearch(true)} className="btn-primary flex items-center gap-2">
            <Search size={15} /> Search Jobs
          </button>
        </div>
      </div>

      <div className="flex items-center gap-2 flex-wrap">
        <div className="flex gap-1 flex-wrap">
          {FILTERS.map(f => (
            <button key={f.id} onClick={() => setFilter(f.id)}
              className={`px-3 py-1.5 rounded-full text-xs font-medium transition-colors border ${
                filter === f.id
                  ? 'bg-brand border-brand text-white'
                  : 'border-surface-border text-slate-400 hover:text-slate-200'
              }`}>{f.label}
            </button>
          ))}
        </div>
        <div className="ml-auto relative">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
          <input className="input pl-8 w-52 py-1.5 text-sm" placeholder="Search titles…"
            value={search} onChange={e => setSearch(e.target.value)} />
        </div>
      </div>

      {apiError && (
        <div className="bg-red-950 border border-red-500/30 text-red-400 text-sm px-4 py-3 rounded-lg">
          Failed to load jobs: {apiError}. Is the API running?
        </div>
      )}

      {loading ? (
        <div className="flex justify-center py-20"><Spinner size="lg" /></div>
      ) : filtered.length === 0 ? (
        <EmptyState
          icon={Briefcase}
          title={jobs.length === 0 ? 'No jobs yet' : 'No jobs match this filter'}
          description={
            jobs.length === 0
              ? 'Click "Search Jobs" to pull jobs from JSearch and start your pipeline.'
              : 'Try a different filter or search term.'
          }
          action={
            jobs.length === 0 && (
              <button onClick={() => setShowSearch(true)} className="btn-primary flex items-center gap-2">
                <Search size={15} /> Search Jobs
              </button>
            )
          }
        />
      ) : (
        <div className="space-y-3">
          {filtered.map(job => (
            <div key={job.job_id} className="card hover:border-slate-600 transition-colors">
              <div className="flex items-start gap-4">
                <ScoreCircle score={job.score} />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <h3 className="font-semibold text-slate-200">
                      {job.parsed_role || job.title || 'Unknown Role'}
                    </h3>
                    <VerdictBadge verdict={job.verdict} />
                  </div>
                  <p className="text-sm text-slate-400 mt-0.5">
                    {job.company} · {job.location}
                  </p>
                  <div className="flex gap-1.5 mt-1.5 flex-wrap">
                    <span className="text-xs text-slate-500 bg-surface px-2 py-0.5 rounded border border-surface-border">{job.source}</span>
                    <span className="text-xs text-slate-500 bg-surface px-2 py-0.5 rounded border border-surface-border">{job.parse_status}</span>
                    {job.date_posted && (
                      <span className="text-xs text-slate-600 bg-surface px-2 py-0.5 rounded border border-surface-border">
                        {job.date_posted}
                      </span>
                    )}
                  </div>
                  {job.rationale && (
                    <p className="text-xs text-slate-500 mt-2 line-clamp-2">{job.rationale}</p>
                  )}
                </div>
              </div>

              <div className="flex gap-2 mt-4 pt-4 border-t border-surface-border flex-wrap">
                {!job.score ? (
                  <button onClick={() => handleScoreOne(job.job_id)}
                    disabled={scoringId === job.job_id}
                    className="btn-secondary btn-sm flex items-center gap-1.5">
                    {scoringId === job.job_id ? <Spinner size="sm" /> : <Zap size={13} />} Score
                  </button>
                ) : (
                  <button onClick={() => handleScoreOne(job.job_id)}
                    disabled={scoringId === job.job_id}
                    className="btn-secondary btn-sm flex items-center gap-1.5">
                    {scoringId === job.job_id ? <Spinner size="sm" /> : '↻'} Re-score
                  </button>
                )}
                <button onClick={() => navigate(`/jobs/${job.job_id}`)}
                  className="btn-secondary btn-sm flex items-center gap-1.5">
                  View <ChevronRight size={13} />
                </button>
                {(job.verdict === 'ASSISTED_APPLY' || job.verdict === 'ELIGIBLE_AUTO_SUBMIT') && (
                  <button onClick={() => navigate(`/jobs/${job.job_id}/artifacts`)}
                    className="btn-primary btn-sm">✨ Artifacts
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {showSearch && (
        <SearchModal
          onClose={() => setShowSearch(false)}
          onSuccess={() => { setShowSearch(false); loadJobs() }}
          api={api}
        />
      )}
      {toast && <Toast {...toast} onClose={() => setToast(null)} />}
    </div>
  )
}
