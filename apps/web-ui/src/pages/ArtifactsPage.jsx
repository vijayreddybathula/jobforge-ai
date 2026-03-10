import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useApi } from '../hooks/useApi'
import { ArrowLeft, Copy, Check, Sparkles } from 'lucide-react'
import Spinner from '../components/common/Spinner'
import Toast from '../components/common/Toast'

function CopyButton({ text }) {
  const [copied, setCopied] = useState(false)
  const copy = () => {
    navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }
  return (
    <button onClick={copy} className="btn-secondary btn-sm flex items-center gap-1.5">
      {copied ? <><Check size={13} className="text-emerald-400" /> Copied!</> : <><Copy size={13} /> Copy</>}
    </button>
  )
}

export default function ArtifactsPage() {
  const { id } = useParams()
  const api = useApi()
  const [jobTitle, setJobTitle] = useState('')
  const [artifacts, setArtifacts] = useState(null)
  const [loading, setLoading] = useState(true)
  const [generating, setGenerating] = useState(false)
  const [toast, setToast] = useState(null)

  useEffect(() => {
    // Fetch job directly by ID instead of loading all 100 jobs
    Promise.all([
      api.get(`/jobs/${id}`).catch(() => null),
      api.get(`/jobs/${id}/artifacts`).catch(() => null),
    ]).then(([job, arts]) => {
      if (job) {
        const role = job.parsed_role || job.title || 'Job'
        const company = job.company || ''
        setJobTitle(company ? `${role} — ${company}` : role)
      }
      if (arts?.artifacts && Object.keys(arts.artifacts).length > 0) setArtifacts(arts.artifacts)
    }).finally(() => setLoading(false))
  }, [id, api])

  const generate = async () => {
    setGenerating(true)
    try {
      const data = await api.post(`/jobs/${id}/artifacts/generate?artifact_types=pitch&artifact_types=resume&artifact_types=answers`)
      setArtifacts(data.artifacts)
      setToast({ message: 'Artifacts generated!' })
    } catch (e) {
      setToast({ message: e.message, type: 'error' })
    } finally { setGenerating(false) }
  }

  if (loading) return <div className="flex justify-center py-20"><Spinner size="lg" /></div>

  return (
    <div className="max-w-3xl space-y-6">
      <Link to={`/jobs/${id}`} className="inline-flex items-center gap-1.5 text-sm text-slate-400 hover:text-slate-200">
        <ArrowLeft size={15} /> Back to Job
      </Link>

      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-100">Application Artifacts</h1>
          <p className="text-slate-400 text-sm mt-1">{jobTitle}</p>
        </div>
        <button onClick={generate} disabled={generating} className="btn-primary flex items-center gap-2 shrink-0">
          {generating ? <><Spinner size="sm" /> Generating...</> : <><Sparkles size={15} /> {artifacts ? 'Regenerate' : 'Generate All'}</>}
        </button>
      </div>

      {!artifacts && !generating && (
        <div className="card text-center py-12">
          <Sparkles size={32} className="mx-auto text-slate-600 mb-3" />
          <p className="text-slate-400 mb-4">Generate your pitch, tailored resume bullets, and application answers</p>
          <button onClick={generate} className="btn-primary">✨ Generate Artifacts</button>
        </div>
      )}

      {generating && <div className="flex justify-center py-12"><div className="text-center"><Spinner size="lg" className="mx-auto mb-3" /><p className="text-sm text-slate-400">GPT-4 generating artifacts...</p></div></div>}

      {artifacts && (
        <div className="space-y-5">
          {/* Pitch */}
          {artifacts.pitch && (
            <div className="card">
              <div className="flex items-center justify-between mb-3">
                <h2 className="font-semibold text-slate-200">🎯 Recruiter Pitch</h2>
                <CopyButton text={artifacts.pitch?.content || artifacts.pitch} />
              </div>
              <p className="text-slate-300 text-sm leading-relaxed">{artifacts.pitch?.content || artifacts.pitch}</p>
            </div>
          )}

          {/* Resume */}
          {artifacts.resume && (
            <div className="card">
              <div className="flex items-center justify-between mb-3">
                <h2 className="font-semibold text-slate-200">📄 Tailored Resume Bullets</h2>
                <CopyButton text={[
                  artifacts.resume.summary,
                  ...(artifacts.resume.bullets || []).map(b => `• ${b}`)
                ].filter(Boolean).join('\n')} />
              </div>
              {artifacts.resume.summary && <p className="text-slate-300 text-sm leading-relaxed mb-4 pb-4 border-b border-surface-border">{artifacts.resume.summary}</p>}
              <div className="space-y-2">
                {(artifacts.resume.bullets || []).map((b, i) => (
                  <div key={i} className="flex gap-2 text-sm">
                    <span className="text-brand mt-0.5 shrink-0">•</span>
                    <span className="text-slate-300 leading-relaxed">{b}</span>
                  </div>
                ))}
              </div>
              {artifacts.resume.bullet_ids_used?.length > 0 && (
                <p className="text-xs text-slate-600 mt-3">Source bullets: {artifacts.resume.bullet_ids_used.join(', ')}</p>
              )}
              {artifacts.resume.keywords_incorporated?.length > 0 && (
                <div className="flex flex-wrap gap-1.5 mt-3">
                  {artifacts.resume.keywords_incorporated.map(k => (
                    <span key={k} className="bg-brand/10 border border-brand/20 text-brand-muted px-2 py-0.5 rounded text-xs">{k}</span>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Answers */}
          {artifacts.answers && (
            <div className="card">
              <h2 className="font-semibold text-slate-200 mb-4">💬 Application Answers</h2>
              <div className="space-y-4">
                {Object.entries(artifacts.answers?.content || artifacts.answers || {}).map(([q, a]) => (
                  <div key={q} className="border-b border-surface-border pb-4 last:border-0">
                    <div className="flex items-center justify-between mb-1.5">
                      <p className="text-xs text-brand uppercase tracking-wider font-medium">{q.replace(/_/g, ' ')}</p>
                      <CopyButton text={a} />
                    </div>
                    <p className="text-sm text-slate-300 leading-relaxed">{a}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {toast && <Toast {...toast} onClose={() => setToast(null)} />}
    </div>
  )
}
