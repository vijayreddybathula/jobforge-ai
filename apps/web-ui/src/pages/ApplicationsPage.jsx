import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useApi } from '../hooks/useApi'
import { BarChart2, ExternalLink } from 'lucide-react'
import Spinner from '../components/common/Spinner'
import Toast from '../components/common/Toast'
import EmptyState from '../components/common/EmptyState'
import VerdictBadge from '../components/jobs/VerdictBadge'

const STAGES = ['phone_screen', 'onsite', 'offer', 'rejected', 'no_response']
const STAGE_LABELS = {
  phone_screen: 'Phone Screen',
  onsite:       'Onsite',
  offer:        'Offer',
  rejected:     'Rejected',
  no_response:  'No Response',
}

// Map application status to a verdict-style key so we can reuse VerdictBadge
const STATUS_VERDICT = {
  submitted: 'ASSISTED_APPLY',
  started:   'VALIDATE',
  cancelled: 'SKIP',
  failed:    'SKIP',
}

export default function ApplicationsPage() {
  const api = useApi()

  const [applications, setApplications] = useState([])
  const [loading,      setLoading]      = useState(true)
  const [feedback,     setFeedback]     = useState(null)
  const [recording,    setRecording]    = useState(null)
  const [apiError,     setApiError]     = useState('')
  const [toast,        setToast]        = useState(null)

  /* ── Load ──────────────────────────────────────────────── */
  useEffect(() => {
    const load = async () => {
      try {
        const apps = await api.get('/applications/')
        setApplications(Array.isArray(apps) ? apps : [])
      } catch (e) {
        setApiError(e.message)
      }
      try {
        const fb = await api.get('/applications/feedback/summary')
        setFeedback(fb)
      } catch {}
      setLoading(false)
    }
    load()
  }, [api])

  /* ── Record outcome ─────────────────────────────────────────── */
  const recordOutcome = async (appId, stage) => {
    setRecording(`${appId}-${stage}`)
    try {
      await api.post(`/applications/${appId}/outcome`, { stage })
      setToast({ message: `Recorded: ${STAGE_LABELS[stage]}` })
      const apps = await api.get('/applications/')
      setApplications(Array.isArray(apps) ? apps : [])
    } catch (e) {
      setToast({ message: e.message, type: 'error' })
    } finally { setRecording(null) }
  }

  /* ── Render ────────────────────────────────────────────────── */
  return (
    <div className="max-w-3xl space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-slate-100">Applications</h1>
        <p className="text-slate-400 text-sm mt-1">Track outcomes and score calibration</p>
      </div>

      {/* API error */}
      {apiError && (
        <div className="bg-red-950 border border-red-500/30 text-red-400 text-sm px-4 py-3 rounded-lg">
          Failed to load applications: {apiError}
        </div>
      )}

      {loading ? (
        <div className="flex justify-center py-12"><Spinner size="lg" /></div>
      ) : applications.length === 0 ? (
        <EmptyState
          icon={BarChart2}
          title="No applications yet"
          description="Once you apply to jobs, they'll appear here. Go to the Jobs page to get started."
          action={
            <Link to="/jobs" className="btn-primary flex items-center gap-2">
              <ExternalLink size={15} /> Go to Jobs
            </Link>
          }
        />
      ) : (
        <div className="space-y-3">
          {applications.map(app => (
            <div key={app.application_id} className="card">
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0">
                  <Link
                    to={`/jobs/${app.job_id}`}
                    className="font-medium text-slate-200 hover:text-brand text-sm transition-colors"
                  >
                    Job → {app.job_id.slice(0, 8)}…
                  </Link>
                  <p className="text-xs text-slate-500 mt-0.5">
                    {app.submitted_at
                      ? `Submitted ${new Date(app.submitted_at).toLocaleDateString()}`
                      : `Started ${new Date(app.created_at).toLocaleDateString()}`
                    }{' · '}{app.apply_mode}
                  </p>
                </div>
                {/* Reuse VerdictBadge instead of duplicating badge CSS */}
                <VerdictBadge verdict={STATUS_VERDICT[app.status] || 'NOT_SCORED'} />
              </div>

              {app.status === 'submitted' && (
                <div className="mt-4 pt-4 border-t border-surface-border">
                  <p className="text-xs text-slate-500 mb-2">Record outcome:</p>
                  <div className="flex gap-2 flex-wrap">
                    {STAGES.map(s => {
                      const key = `${app.application_id}-${s}`
                      return (
                        <button key={s}
                          onClick={() => recordOutcome(app.application_id, s)}
                          disabled={recording === key}
                          className={`text-xs px-3 py-1.5 rounded-full border font-medium transition-colors ${
                            s === 'offer'
                              ? 'bg-emerald-900/30 border-emerald-500/30 text-emerald-400 hover:bg-emerald-900/60'
                              : s === 'rejected'
                                ? 'bg-red-900/30 border-red-500/30 text-red-400 hover:bg-red-900/60'
                                : 'bg-surface border-surface-border text-slate-400 hover:bg-surface-hover'
                          }`}>
                          {recording === key ? <Spinner size="sm" /> : STAGE_LABELS[s]}
                        </button>
                      )
                    })}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Feedback / calibration */}
      {feedback && (feedback.total_with_feedback ?? 0) > 0 && (
        <div className="card">
          <h2 className="font-semibold text-slate-200 mb-4">Score Calibration</h2>
          <div className="space-y-3">
            {Object.entries(feedback.score_band_performance || {}).map(([band, data]) => (
              <div key={band} className="flex items-center justify-between text-sm">
                <span className="text-slate-400">Score {band}</span>
                <div className="flex items-center gap-4">
                  <span className="text-slate-500">{data.count} applied</span>
                  <span className="text-emerald-400 font-medium">{data.callback_rate} callbacks</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {feedback && (feedback.total_with_feedback ?? 0) === 0 && applications.length > 0 && (
        <div className="card">
          <h2 className="font-semibold text-slate-200 mb-2">Score Calibration</h2>
          <p className="text-sm text-slate-500">
            Record outcomes (phone screen, offer, rejected) on your submitted applications
            to start building your score calibration data.
          </p>
        </div>
      )}

      {toast && <Toast {...toast} onClose={() => setToast(null)} />}
    </div>
  )
}
