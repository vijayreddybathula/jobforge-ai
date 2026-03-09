import { useEffect, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useApi } from '../hooks/useApi'
import { Search, Zap, Briefcase, ChevronRight } from 'lucide-react'
import VerdictBadge from '../components/jobs/VerdictBadge'
import ScoreCircle from '../components/jobs/ScoreCircle'
import Spinner from '../components/common/Spinner'
import Toast from '../components/common/Toast'
import EmptyState from '../components/common/EmptyState'

/* ── Search modal ──────────────────────────────────────────────── */
function SearchModal({ onClose, onSuccess, api }) {
  const [form, setForm] = useState({
    keywords: 'Senior GenAI Engineer',
    location: 'Dallas, TX',
    work_type: 'remote,hybrid',
    max_results: 10,
  })
  const [loading, setLoading] = useState(false)
  const [result,  setResult]  = useState(null)
  const set = k => e => setForm(f => ({ ...f, [k]: e.target.value }))

  const search = async () => {
    setLoading(true)
    setResult(null)
    try {
      const params = new URLSearchParams({
        keywords:     form.keywords,
        location:     form.location,
        work_type:    form.work_type,
        max_results:  form.max_results,
        auto_parse:   true,
      })
      const data = await api.post(`/jobs/search?${params}`)
      setResult(data)
      if ((data.ingested ?? 0) > 0 || (data.reparsed ?? 0) > 0 || (data.parsed ?? 0) > 0) {
        onSuccess()
      }
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

        <div className="space-y-4">
          <div><label className="label">Keywords</label>
            <input className="input" value={form.keywords} onChange={set('keywords')} /></div>
          <div><label className="label">Location</label>
            <input className="input" value={form.location} onChange={set('location')} /></div>
          <div>
            <label className="label">Work Type</label>
            <select className="input" value={form.work_type} onChange={set('work_type')}>
              <option value="remote,hybrid">Remote + Hybrid</option>
              <option value="remote">Remote only</option>
              <option value="hybrid">Hybrid only</option>
              <option value="onsite">Onsite</option>
            </select>
          </div>
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
                : `✓ Fetched ${result.total_fetched ?? 0} · Ingested ${result.ingested ?? 0} · Parsed ${result.parsed ?? 0}`
              }
            </div>
          )}

          <button onClick={search} disabled={loading}
            className="btn-primary w-full flex items-center justify-center gap-2 py-2.5">
            {loading ? <><Spinner size="sm" /> Searching…</> : <><Search size={15} /> Search & Ingest</>}
          </button>
        </div>
      </div>
    </div>
  )
}

/* ── Jobs page ─────────────────────────────────────────────────── */
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

  /* ── Load ──────────────────────────────────────────────────── */
  const loadJobs = useCallback(async () => {
    setLoading(true)
    setApiError('')
    try {
      const data = await api.get('/jobs/?page=1&limit=50')
      setJobs(data.jobs || [])
      setTotal(data.total || 0)
    } catch (e) {
      setApiError(e.message)
    } finally { setLoading(false) }
  }, [api])

  useEffect(() => { loadJobs() }, [loadJobs])

  /* ── Score one ─────────────────────────────────────────────── */
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

  /* ── Score all ─────────────────────────────────────────────── */
  const handleScoreAll = async () => {
    setScoring(true)
    try {
      const r = await api.post('/jobs/score-all')
      setToast({ message: `Scored ${r.scored} new jobs. Skipped ${r.skipped_already_scored} already scored.` })
      await loadJobs()
    } catch (e) {
      setToast({ message: e.message, type: 'error' })
    } finally { setScoring(false) }
  }

  /* ── Filter / search ───────────────────────────────────────── */
  const FILTERS = [
    { id: 'all',                  label: 'All' },
    { id: 'NOT_SCORED',           label: 'Unscored' },
    { id: 'ASSISTED_APPLY',       label: 'Apply' },
    { id: 'ELIGIBLE_AUTO_SUBMIT', label: 'Auto' },
    { id: 'VALIDATE',             label: 'Validate' },
    { id: 'SKIP',                 label: 'Skip' },
  ]

  const filtered = jobs.filter(j => {
    if (filter !== 'all' && j.verdict !== filter) return false
    if (search) {
      const q = search.toLowerCase()
      if (!`${j.title || ''} ${j.company || ''} ${j.parsed_role || ''}`.toLowerCase().includes(q)) return false
    }
    return true
  })

  /* ── Render ────────────────────────────────────────────────── */
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-100">Job Pipeline</h1>
          <p className="text-slate-400 text-sm mt-1">{total} jobs in catalog</p>
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

      {/* Filters */}
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

      {/* API error */}
      {apiError && (
        <div className="bg-red-950 border border-red-500/30 text-red-400 text-sm px-4 py-3 rounded-lg">
          Failed to load jobs: {apiError}. Is the API running?
        </div>
      )}

      {/* Job list */}
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
