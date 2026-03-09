import { useEffect, useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { useApi } from '../hooks/useApi'
import { ArrowLeft, Zap, Sparkles } from 'lucide-react'
import VerdictBadge from '../components/jobs/VerdictBadge'
import ScoreCircle from '../components/jobs/ScoreCircle'
import Spinner from '../components/common/Spinner'
import Toast from '../components/common/Toast'

export default function JobDetailPage() {
  const { id } = useParams()
  const api = useApi()
  const navigate = useNavigate()
  const [job, setJob] = useState(null)
  const [parsed, setParsed] = useState(null)
  const [score, setScore] = useState(null)
  const [loading, setLoading] = useState(true)
  const [scoring, setScoring] = useState(false)
  const [toast, setToast] = useState(null)

  useEffect(() => {
    Promise.all([
      api.get(`/jobs/?limit=100`).then(d => d.jobs?.find(j => j.job_id === id)),
      api.get(`/jobs/${id}/parsed`).catch(() => null),
      api.get(`/jobs/${id}/score`).catch(() => null),
    ]).then(([jobData, parsedData, scoreData]) => {
      setJob(jobData)
      setParsed(parsedData?.parsed_jd)
      setScore(scoreData)
    }).finally(() => setLoading(false))
  }, [id])

  const handleScore = async () => {
    setScoring(true)
    try {
      const s = await api.post(`/jobs/${id}/score`)
      setScore(s)
      setJob(j => j ? { ...j, score: s.total_score, verdict: s.verdict } : j)
      setToast({ message: `Scored: ${s.total_score}/100 — ${s.verdict}` })
    } catch (e) {
      setToast({ message: e.message, type: 'error' })
    } finally { setScoring(false) }
  }

  if (loading) return <div className="flex justify-center py-20"><Spinner size="lg" /></div>
  if (!job) return <div className="text-slate-400">Job not found.</div>

  const scoreData = score || job
  const breakdown = scoreData?.breakdown || {}
  const cleanBreakdown = Object.fromEntries(Object.entries(breakdown).filter(([k]) => !k.startsWith('_')))

  return (
    <div className="max-w-5xl space-y-6">
      <Link to="/jobs" className="inline-flex items-center gap-1.5 text-sm text-slate-400 hover:text-slate-200">
        <ArrowLeft size={15} /> Back to Jobs
      </Link>

      {/* Header */}
      <div className="card">
        <div className="flex items-start gap-4">
          <ScoreCircle score={scoreData?.total_score || scoreData?.score} size="lg" />
          <div className="flex-1">
            <h1 className="text-xl font-bold text-slate-100">{parsed?.role || job.parsed_role || job.title}</h1>
            <p className="text-slate-400 mt-1">{job.company} · {job.location} · {job.source}</p>
            <div className="flex items-center gap-2 mt-3">
              <VerdictBadge verdict={scoreData?.verdict || job.verdict} />
            </div>
          </div>
        </div>
        <div className="flex gap-2 mt-5 pt-5 border-t border-surface-border">
          <button onClick={handleScore} disabled={scoring} className="btn-secondary flex items-center gap-2">
            {scoring ? <><Spinner size="sm" /> Scoring...</> : <><Zap size={15} /> {score ? 'Re-score' : 'Score'}</>}
          </button>
          {(job.verdict === 'ASSISTED_APPLY' || scoreData?.verdict === 'ASSISTED_APPLY' || scoreData?.verdict === 'ELIGIBLE_AUTO_SUBMIT') && (
            <button onClick={() => navigate(`/jobs/${id}/artifacts`)} className="btn-primary flex items-center gap-2">
              <Sparkles size={15} /> Generate Artifacts
            </button>
          )}
        </div>
      </div>

      <div className="grid md:grid-cols-2 gap-6">
        {/* Score breakdown */}
        {Object.keys(cleanBreakdown).length > 0 && (
          <div className="card">
            <h2 className="font-semibold text-slate-200 mb-4">Score Breakdown</h2>
            <div className="space-y-3">
              {Object.entries(cleanBreakdown).map(([k, v]) => (
                <div key={k}>
                  <div className="flex justify-between text-sm mb-1">
                    <span className="text-slate-400 capitalize">{k.replace(/_/g, ' ')}</span>
                    <span className="font-medium text-slate-200">{v}</span>
                  </div>
                  <div className="h-1.5 bg-surface rounded-full overflow-hidden">
                    <div className="h-full rounded-full transition-all" style={{
                      width: `${v}%`,
                      background: v >= 80 ? '#6366f1' : v >= 60 ? '#10b981' : v >= 40 ? '#f59e0b' : '#ef4444'
                    }} />
                  </div>
                </div>
              ))}
            </div>
            {scoreData?.rationale && (
              <p className="text-xs text-slate-500 mt-4 leading-relaxed">{scoreData.rationale}</p>
            )}
          </div>
        )}

        {/* Parsed JD */}
        {parsed && (
          <div className="card">
            <h2 className="font-semibold text-slate-200 mb-4">Parsed Job Description</h2>
            <div className="space-y-3 text-sm">
              <div><span className="text-slate-500">Role: </span><span className="text-slate-200">{parsed.role}</span></div>
              <div><span className="text-slate-500">Seniority: </span><span className="text-slate-200">{parsed.seniority}</span></div>
              {parsed.must_have_skills?.length > 0 && (
                <div>
                  <p className="text-slate-500 mb-1.5">Must-haves:</p>
                  <div className="flex flex-wrap gap-1.5">
                    {parsed.must_have_skills.map(s => <span key={s} className="bg-surface border border-surface-border text-slate-300 px-2 py-0.5 rounded text-xs">{s}</span>)}
                  </div>
                </div>
              )}
              {parsed.ats_keywords?.length > 0 && (
                <div>
                  <p className="text-slate-500 mb-1.5">ATS Keywords:</p>
                  <div className="flex flex-wrap gap-1.5">
                    {parsed.ats_keywords.slice(0, 10).map(k => <span key={k} className="bg-brand/10 border border-brand/20 text-brand-muted px-2 py-0.5 rounded text-xs">{k}</span>)}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {toast && <Toast {...toast} onClose={() => setToast(null)} />}
    </div>
  )
}
