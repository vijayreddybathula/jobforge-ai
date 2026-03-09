import { useEffect, useState, useRef } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { useApi } from '../hooks/useApi'
import { ArrowLeft, Zap, Sparkles, ExternalLink, AlertCircle } from 'lucide-react'
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

export default function JobDetailPage() {
  const { id }   = useParams()
  const api      = useApi()
  const navigate = useNavigate()
  const didLoad  = useRef(false)

  const [job,      setJob]      = useState(null)
  const [parsed,   setParsed]   = useState(null)
  const [score,    setScore]    = useState(null)
  const [loading,  setLoading]  = useState(true)
  const [scoring,  setScoring]  = useState(false)
  const [apiError, setApiError] = useState('')
  const [toast,    setToast]    = useState(null)

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
      setScoring(false)
    }
  }

  /* ── Loading ──────────────────────────────────────────────── */
  if (loading) return (
    <div className="flex justify-center py-20"><Spinner size="lg" /></div>
  )

  /* ── Error from API ───────────────────────────────────────── */
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

  /* ── Job not found ────────────────────────────────────────── */
  if (!job) return (
    <div className="max-w-2xl">
      <Link to="/jobs" className="inline-flex items-center gap-1.5 text-sm text-slate-400 hover:text-slate-200 mb-6">
        <ArrowLeft size={15} /> Back to Jobs
      </Link>
      <div className="card text-slate-400 text-sm">Job not found.</div>
    </div>
  )

  /* ── Derive display values safely ─────────────────────────── */
  const totalScore     = score?.total_score ?? job.score ?? null
  const verdict        = score?.verdict     ?? job.verdict ?? 'NOT_SCORED'
  const breakdown      = score?.breakdown   ?? job.breakdown ?? {}
  const rationale      = score?.rationale   ?? job.rationale ?? null
  const cleanBreakdown = Object.entries(breakdown).filter(([k]) => !k.startsWith('_'))

  /* ── Render ───────────────────────────────────────────────── */
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
            {job.source_url && job.source_url !== 'null' && (
              <a
                href={job.source_url}
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

        <div className="flex gap-2 mt-5 pt-5 border-t border-surface-border flex-wrap">
          <button onClick={handleScore} disabled={scoring} className="btn-secondary flex items-center gap-2">
            {scoring
              ? <><Spinner size="sm" /> Scoring…</>
              : <><Zap size={15} /> {score ? 'Re-score' : 'Score'}</>}
          </button>
          {(verdict === 'ASSISTED_APPLY' || verdict === 'ELIGIBLE_AUTO_SUBMIT') && (
            <button onClick={() => navigate(`/jobs/${id}/artifacts`)} className="btn-primary flex items-center gap-2">
              <Sparkles size={15} /> Generate Artifacts
            </button>
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
              {scoring
                ? <><Spinner size="sm" /> Parsing & Scoring…</>
                : <><Zap size={15} /> Score to Parse</>}
            </button>
          </div>
        )}
      </div>

      {toast && <Toast {...toast} onClose={() => setToast(null)} />}
    </div>
  )
}
