import { useEffect, useState, useRef } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { useApi } from '../hooks/useApi'
import { ArrowLeft, Zap, ExternalLink, AlertCircle, Send, CheckCircle, Copy, Check } from 'lucide-react'
import VerdictBadge from '../components/jobs/VerdictBadge'
import ScoreCircle from '../components/jobs/ScoreCircle'
import Spinner from '../components/common/Spinner'
import Toast from '../components/common/Toast'

const BREAKDOWN_LABELS = {
  compensation:        'Compensation',
  location_fit:        'Location Fit',
  domain_industry:     'Domain / Industry',
  core_skill_match:    'Core Skill Match',
  nice_to_have_skills: 'Nice-to-Have Skills',
  seniority_alignment: 'Seniority Alignment',
}

function SkillChips({ skills, variant = 'default' }) {
  if (!Array.isArray(skills) || skills.length === 0) return null
  const cls =
    variant === 'brand' ? 'bg-brand/10 border-brand/20 text-brand-muted'
    : variant === 'soft'  ? 'bg-emerald-900/20 border-emerald-500/20 text-emerald-300'
    : 'bg-surface border-surface-border text-slate-300'
  return (
    <div className="flex flex-wrap gap-1.5">
      {skills.map((s, i) => (
        <span key={`${s}-${i}`} className={`border px-2 py-0.5 rounded text-xs ${cls}`}>{s}</span>
      ))}
    </div>
  )
}

/* ── Copy-to-clipboard helper ─────────────────────────────────── */
function CopyField({ label, value }) {
  const [copied, setCopied] = useState(false)
  if (!value) return null
  const copy = () => {
    navigator.clipboard.writeText(value)
    setCopied(true)
    setTimeout(() => setCopied(false), 1800)
  }
  return (
    <div className="flex items-center justify-between gap-2 bg-surface border border-surface-border rounded-lg px-3 py-2">
      <div className="min-w-0">
        <p className="text-xs text-slate-500 mb-0.5">{label}</p>
        <p className="text-sm text-slate-200 truncate">{value}</p>
      </div>
      <button onClick={copy} className="shrink-0 text-slate-500 hover:text-slate-200 transition-colors">
        {copied ? <Check size={14} className="text-emerald-400" /> : <Copy size={14} />}
      </button>
    </div>
  )
}

/* ── Assisted Apply Modal ─────────────────────────────────────── */
function ApplyModal({ job, api, onClose }) {
  const [ctx,       setCtx]       = useState(null)
  const [loading,   setLoading]   = useState(true)
  const [started,   setStarted]   = useState(false)
  const [submitted, setSubmitted] = useState(false)
  const [error,     setError]     = useState(null)

  useEffect(() => {
    api.get(`/jobs/${job.job_id}/apply/context`)
      .then(d => { setCtx(d); setLoading(false) })
      .catch(e => { setError(e.message); setLoading(false) })
  }, [job.job_id, api])

  const handleOpenAndStart = async () => {
    // 1. Open the direct apply URL in a new tab
    window.open(ctx.apply_url, '_blank', 'noopener,noreferrer')
    // 2. Record the start in our DB
    try {
      await api.post(`/jobs/${job.job_id}/apply/start`)
      setStarted(true)
    } catch (e) {
      // Non-fatal — the tab is open, log only
      console.warn('apply/start failed:', e.message)
      setStarted(true)
    }
  }

  const handleMarkSubmitted = async () => {
    try {
      await api.post(`/jobs/${job.job_id}/apply/submit`)
      setSubmitted(true)
    } catch (e) {
      setError(e.message)
    }
  }

  return (
    <div
      className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4"
      onClick={e => e.target === e.currentTarget && onClose()}
    >
      <div className="bg-surface-card border border-surface-border rounded-2xl w-full max-w-lg p-6 space-y-5 max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-start justify-between">
          <div>
            <h2 className="text-lg font-semibold text-slate-100">Assisted Apply</h2>
            <p className="text-slate-400 text-sm mt-0.5">{job.company} · {job.parsed_role || job.title}</p>
          </div>
          <button onClick={onClose} className="text-slate-500 hover:text-slate-300 text-xl leading-none ml-4">×</button>
        </div>

        {loading && <div className="flex justify-center py-8"><Spinner size="md" /></div>}

        {error && (
          <div className="bg-red-950 border border-red-500/30 text-red-400 text-sm px-3 py-2 rounded-lg">
            {error}
          </div>
        )}

        {ctx && !submitted && (
          <>
            {/* Step 1 — open form */}
            {!started ? (
              <>
                <p className="text-slate-400 text-sm">
                  We'll open the application form in a new tab. Use the pre-filled
                  values below to fill it quickly, then come back and mark it submitted.
                </p>
                <div className="space-y-2">
                  <CopyField label="First Name" value={ctx.prefill.first_name} />
                  <CopyField label="Last Name"  value={ctx.prefill.last_name}  />
                  <CopyField label="Email"      value={ctx.prefill.email}      />
                  {ctx.pitch && (
                    <div className="bg-surface border border-surface-border rounded-lg px-3 py-2">
                      <div className="flex items-center justify-between mb-1">
                        <p className="text-xs text-slate-500">Cover Letter / Pitch</p>
                        <button
                          onClick={() => navigator.clipboard.writeText(ctx.pitch)}
                          className="text-slate-500 hover:text-slate-200"
                        ><Copy size={13} /></button>
                      </div>
                      <p className="text-xs text-slate-400 leading-relaxed line-clamp-4">{ctx.pitch}</p>
                    </div>
                  )}
                  {!ctx.pitch && (
                    <p className="text-xs text-slate-600 italic">
                      No pitch generated yet — generate artifacts first for a tailored cover letter.
                    </p>
                  )}
                </div>
                <button
                  onClick={handleOpenAndStart}
                  className="btn-primary w-full flex items-center justify-center gap-2 py-2.5"
                >
                  <ExternalLink size={15} /> Open Application Form
                </button>
              </>
            ) : (
              /* Step 2 — after form is open */
              <>
                <div className="bg-emerald-950 border border-emerald-500/30 rounded-lg px-3 py-2 text-sm text-emerald-300">
                  ✓ Application form opened. Fill it in, then click below when you've submitted.
                </div>
                <div className="space-y-2">
                  <CopyField label="First Name" value={ctx.prefill.first_name} />
                  <CopyField label="Last Name"  value={ctx.prefill.last_name}  />
                  <CopyField label="Email"      value={ctx.prefill.email}      />
                  {ctx.pitch && (
                    <div className="bg-surface border border-surface-border rounded-lg px-3 py-2">
                      <div className="flex items-center justify-between mb-1">
                        <p className="text-xs text-slate-500">Cover Letter / Pitch</p>
                        <button
                          onClick={() => navigator.clipboard.writeText(ctx.pitch)}
                          className="text-slate-500 hover:text-slate-200"
                        ><Copy size={13} /></button>
                      </div>
                      <p className="text-xs text-slate-400 leading-relaxed line-clamp-4">{ctx.pitch}</p>
                    </div>
                  )}
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => window.open(ctx.apply_url, '_blank', 'noopener,noreferrer')}
                    className="btn-secondary flex-1 flex items-center justify-center gap-1.5"
                  >
                    <ExternalLink size={13} /> Re-open Form
                  </button>
                  <button
                    onClick={handleMarkSubmitted}
                    className="btn-primary flex-1 flex items-center justify-center gap-1.5"
                  >
                    <Send size={13} /> Mark Submitted
                  </button>
                </div>
              </>
            )}
          </>
        )}

        {submitted && (
          <div className="text-center py-6 space-y-3">
            <CheckCircle size={40} className="text-emerald-400 mx-auto" />
            <p className="text-slate-200 font-semibold">Application Submitted!</p>
            <p className="text-slate-400 text-sm">Tracked in your pipeline. Good luck! 🎯</p>
            <button onClick={onClose} className="btn-primary mt-2">Done</button>
          </div>
        )}
      </div>
    </div>
  )
}

/* ── Job Detail Page ──────────────────────────────────────────── */
export default function JobDetailPage() {
  const { id }   = useParams()
  const api      = useApi()
  const navigate = useNavigate()
  const didLoad  = useRef(false)

  const [job,       setJob]       = useState(null)
  const [parsed,    setParsed]    = useState(null)
  const [score,     setScore]     = useState(null)
  const [loading,   setLoading]   = useState(true)
  const [scoring,   setScoring]   = useState(false)
  const [showApply, setShowApply] = useState(false)
  const [apiError,  setApiError]  = useState('')
  const [toast,     setToast]     = useState(null)

  useEffect(() => {
    if (didLoad.current) return
    didLoad.current = true
    const load = async () => {
      try {
        const [jobData, parsedData, scoreData] = await Promise.all([
          api.get(`/jobs/${id}`),
          api.get(`/jobs/${id}/parsed`).catch(() => null),
          api.get(`/jobs/${id}/score`).catch(() => null),
        ])
        setJob(jobData)
        setParsed(parsedData?.parsed_jd ?? null)
        setScore(scoreData ?? null)
      } catch (e) {
        setApiError(e?.message || 'Failed to load job')
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [id])

  const handleScore = async () => {
    setScoring(true)
    try {
      const s = await api.post(`/jobs/${id}/score`)
      setScore(s)
      setJob(j => j ? { ...j, score: s.total_score, verdict: s.verdict } : j)
      if (!parsed) {
        const p = await api.get(`/jobs/${id}/parsed`).catch(() => null)
        setParsed(p?.parsed_jd ?? null)
      }
      setToast({ message: `Scored: ${s.total_score}/100 — ${s.verdict}` })
    } catch (e) {
      setToast({ message: e?.message || 'Scoring failed', type: 'error' })
    } finally {
      setScoring(false) }
  }

  if (loading) return <div className="flex justify-center py-20"><Spinner size="lg" /></div>

  if (apiError) return (
    <div className="max-w-2xl">
      <Link to="/jobs" className="inline-flex items-center gap-1.5 text-sm text-slate-400 hover:text-slate-200 mb-6">
        <ArrowLeft size={15} /> Back to Jobs
      </Link>
      <div className="card flex items-start gap-3">
        <AlertCircle size={18} className="text-red-400 shrink-0 mt-0.5" />
        <div>
          <p className="text-slate-200 font-medium">Failed to load job</p>
          <p className="text-slate-400 text-sm mt-1">{apiError}</p>
        </div>
      </div>
    </div>
  )

  if (!job) return (
    <div className="max-w-2xl">
      <Link to="/jobs" className="inline-flex items-center gap-1.5 text-sm text-slate-400 hover:text-slate-200 mb-6">
        <ArrowLeft size={15} /> Back to Jobs
      </Link>
      <div className="card text-slate-400 text-sm">Job not found.</div>
    </div>
  )

  const totalScore     = score?.total_score ?? job.score ?? null
  const verdict        = score?.verdict     ?? job.verdict ?? 'NOT_SCORED'
  const breakdown      = score?.breakdown   ?? job.breakdown ?? {}
  const rationale      = score?.rationale   ?? job.rationale ?? null
  const cleanBreakdown = Object.entries(breakdown).filter(([k]) => !k.startsWith('_'))

  // Apply URL: prefer apply_link (direct ATS) over source_url
  const applyUrl = job.apply_link || job.source_url

  const canApply = verdict === 'ASSISTED_APPLY' || verdict === 'ELIGIBLE_AUTO_SUBMIT' || totalScore >= 50

  return (
    <div className="max-w-5xl space-y-6">
      <Link to="/jobs" className="inline-flex items-center gap-1.5 text-sm text-slate-400 hover:text-slate-200">
        <ArrowLeft size={15} /> Back to Jobs
      </Link>

      {/* Header card */}
      <div className="card">
        <div className="flex items-start gap-4">
          <ScoreCircle score={totalScore} size="lg" />
          <div className="flex-1 min-w-0">
            <h1 className="text-xl font-bold text-slate-100 leading-tight">
              {parsed?.role || job.parsed_role || job.title || 'Unknown Role'}
            </h1>
            <p className="text-slate-400 mt-1 text-sm">
              {[job.company, job.location, job.source].filter(Boolean).join(' · ')}
            </p>
            {job.posted_at && (
              <p className="text-xs text-slate-600 mt-0.5">
                Posted {new Date(job.posted_at).toLocaleDateString()}
              </p>
            )}
            {applyUrl && (
              <a
                href={applyUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-xs text-brand hover:text-brand-hover mt-1.5"
              >
                View original posting <ExternalLink size={11} />
              </a>
            )}
            <div className="flex items-center gap-2 mt-3">
              <VerdictBadge verdict={verdict} />
            </div>
          </div>
        </div>

        {/* Action bar */}
        <div className="flex gap-2 mt-5 pt-5 border-t border-surface-border flex-wrap">
          <button onClick={handleScore} disabled={scoring} className="btn-secondary flex items-center gap-2">
            {scoring
              ? <><Spinner size="sm" /> Scoring…</>
              : <><Zap size={15} /> {score ? 'Re-score' : 'Score'}</>}
          </button>

          {/* Apply button — always visible once job is loaded, disabled if no score */}
          {totalScore !== null ? (
            <button
              onClick={() => setShowApply(true)}
              className={`flex items-center gap-2 ${
                canApply ? 'btn-primary' : 'btn-secondary opacity-60'
              }`}
            >
              <Send size={15} />
              {canApply ? 'Apply Now' : 'Apply (low match)'}
            </button>
          ) : (
            <button disabled className="btn-secondary flex items-center gap-2 opacity-40">
              <Send size={15} /> Apply (score first)
            </button>
          )}

          {/* Direct link as fallback */}
          {applyUrl && (
            <a
              href={applyUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="btn-secondary flex items-center gap-2"
            >
              <ExternalLink size={15} /> Open Posting
            </a>
          )}
        </div>
      </div>

      <div className="grid md:grid-cols-2 gap-6">
        {/* Score breakdown */}
        {cleanBreakdown.length > 0 && (
          <div className="card">
            <h2 className="font-semibold text-slate-200 mb-4">Score Breakdown</h2>
            <div className="space-y-3">
              {cleanBreakdown.map(([k, v]) => (
                <div key={k}>
                  <div className="flex justify-between text-sm mb-1">
                    <span className="text-slate-400">{BREAKDOWN_LABELS[k] || k.replace(/_/g, ' ')}</span>
                    <span className="font-medium text-slate-200">{v}</span>
                  </div>
                  <div className="h-1.5 bg-surface rounded-full overflow-hidden">
                    <div className="h-full rounded-full transition-all" style={{
                      width: `${Math.min(100, Math.max(0, v))}%`,
                      background: v >= 80 ? '#6366f1' : v >= 60 ? '#10b981' : v >= 40 ? '#f59e0b' : '#ef4444',
                    }} />
                  </div>
                </div>
              ))}
            </div>
            {rationale && (
              <p className="text-xs text-slate-500 mt-4 leading-relaxed">{rationale}</p>
            )}
          </div>
        )}

        {/* Parsed JD */}
        {parsed ? (
          <div className="card space-y-4">
            <h2 className="font-semibold text-slate-200">Parsed Job Description</h2>
            <div className="space-y-3 text-sm">
              <div className="grid grid-cols-2 gap-2">
                {parsed.role && (
                  <div><span className="text-slate-500">Role </span>
                    <span className="text-slate-200 font-medium">{parsed.role}</span></div>
                )}
                {parsed.seniority && (
                  <div><span className="text-slate-500">Seniority </span>
                    <span className="text-slate-200 font-medium">{parsed.seniority}</span></div>
                )}
              </div>
              {(parsed.salary_range?.min || parsed.salary_range?.max) && (
                <div>
                  <span className="text-slate-500">Salary </span>
                  <span className="text-slate-200 font-medium">
                    ${(parsed.salary_range.min || 0).toLocaleString()}
                    {parsed.salary_range.max ? ` – $${parsed.salary_range.max.toLocaleString()}` : '+'}
                  </span>
                </div>
              )}
              {parsed.must_have_skills?.length > 0 && (
                <div>
                  <p className="text-slate-500 mb-1.5">Must-haves</p>
                  <SkillChips skills={parsed.must_have_skills} />
                </div>
              )}
              {parsed.nice_to_have_skills?.length > 0 && (
                <div>
                  <p className="text-slate-500 mb-1.5">Nice-to-haves</p>
                  <SkillChips skills={parsed.nice_to_have_skills} variant="soft" />
                </div>
              )}
              {parsed.ats_keywords?.length > 0 && (
                <div>
                  <p className="text-slate-500 mb-1.5">ATS Keywords</p>
                  <SkillChips skills={parsed.ats_keywords} variant="brand" />
                </div>
              )}
              {parsed.responsibilities?.length > 0 && (
                <div>
                  <p className="text-slate-500 mb-1.5">Responsibilities</p>
                  <ul className="space-y-1 list-disc list-inside text-slate-300">
                    {parsed.responsibilities.map((r, i) => (
                      <li key={i} className="text-xs leading-relaxed">{r}</li>
                    ))}
                  </ul>
                </div>
              )}
              {parsed.summary && (
                <div>
                  <p className="text-slate-500 mb-1">Summary</p>
                  <p className="text-slate-400 text-xs leading-relaxed">{parsed.summary}</p>
                </div>
              )}
            </div>
          </div>
        ) : (
          <div className="card flex flex-col items-center justify-center py-10 text-center">
            <p className="text-slate-400 text-sm mb-3">This job hasn't been scored yet.</p>
            <p className="text-slate-500 text-xs mb-4">Scoring will auto-parse the job description.</p>
            <button onClick={handleScore} disabled={scoring} className="btn-primary flex items-center gap-2">
              {scoring ? <><Spinner size="sm" /> Parsing & Scoring…</> : <><Zap size={15} /> Score to Parse</>}
            </button>
          </div>
        )}
      </div>

      {showApply && (
        <ApplyModal
          job={{ ...job, parsed_role: parsed?.role }}
          api={api}
          onClose={() => setShowApply(false)}
        />
      )}

      {toast && <Toast {...toast} onClose={() => setToast(null)} />}
    </div>
  )
}
