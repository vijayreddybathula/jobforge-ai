import { useEffect, useState } from 'react'
import { useApi } from '../hooks/useApi'
import { Mail, AlertCircle } from 'lucide-react'
import Spinner from '../components/common/Spinner'
import Toast from '../components/common/Toast'
import EmptyState from '../components/common/EmptyState'

const STAGES = ['phone_screen', 'onsite', 'offer', 'rejected', 'no_response']
const STAGE_LABELS = {
  phone_screen: 'Phone Screen',
  onsite:       'Onsite',
  offer:        'Offer',
  rejected:     'Rejected',
  no_response:  'No Response',
}

const STATUS_BADGE = {
  submitted: 'bg-emerald-900/30 border-emerald-500/30 text-emerald-400',
  started:   'bg-amber-900/30  border-amber-500/30  text-amber-400',
  cancelled: 'bg-red-900/30    border-red-500/30    text-red-400',
  failed:    'bg-red-900/30    border-red-500/30    text-red-400',
}

export default function ApplicationsPage() {
  const api = useApi()
  const [applications, setApplications] = useState([])
  const [loading,      setLoading]      = useState(true)
  const [error,        setError]        = useState('')
  const [feedback,     setFeedback]     = useState(null)
  const [recording,    setRecording]    = useState(null)
  const [toast,        setToast]        = useState(null)

  /* ── load ──────────────────────────────────────────────────────── */
  useEffect(() => {
    const load = async () => {
      try {
        const [apps, fb] = await Promise.allSettled([
          api.get('/applications/'),
          api.get('/applications/feedback/summary'),
        ])
        if (apps.status === 'fulfilled') {
          setApplications(Array.isArray(apps.value) ? apps.value : [])
        } else {
          setError(apps.reason?.message || 'Failed to load applications.')
        }
        if (fb.status === 'fulfilled') setFeedback(fb.value)
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  /* ── record outcome ─────────────────────────────────────────── */
  const recordOutcome = async (appId, stage) => {
    setRecording(appId + stage)
    try {
      await api.post(`/applications/${appId}/outcome`, { stage })
      setToast({ message: `Outcome recorded: ${STAGE_LABELS[stage]}` })
      // Refresh list
      const apps = await api.get('/applications/')
      setApplications(Array.isArray(apps) ? apps : [])
    } catch (e) {
      setToast({ message: e.message, type: 'error' })
    } finally {
      setRecording(null)
    }
  }

  /* ── render ─────────────────────────────────────────────────── */
  return (
    <div className="max-w-3xl space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-slate-100">Applications</h1>
        <p className="text-slate-400 text-sm mt-1">Track outcomes and score calibration</p>
      </div>

      {loading ? (
        <div className="flex justify-center py-12"><Spinner size="lg" /></div>
      ) : error ? (
        <div className="card flex items-center gap-3 text-red-400 border-red-500/30">
          <AlertCircle size={18} />
          <div>
            <p className="font-medium">Could not load applications</p>
            <p className="text-sm text-red-400/70 mt-0.5">{error}</p>
          </div>
        </div>
      ) : applications.length === 0 ? (
        <EmptyState
          icon={Mail}
          title="No applications yet"
          description="Apply to a job first. After submitting you can track phone screens, onsites, and offers here."
        />
      ) : (
        <div className="space-y-3">
          {applications.map(app => (
            <div key={app.application_id} className="card">
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-slate-200 text-sm truncate">
                    Job: <span className="font-mono text-slate-400">{app.job_id?.slice(0, 8)}…</span>
                  </p>
                  <p className="text-xs text-slate-500 mt-0.5">
                    {app.submitted_at
                      ? `Submitted ${new Date(app.submitted_at).toLocaleDateString()}`
                      : `Started ${new Date(app.created_at).toLocaleDateString()}`
                    }
                    {' · '}{app.apply_mode}
                  </p>
                </div>
                <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold border shrink-0 ${
                  STATUS_BADGE[app.status] || 'bg-surface border-surface-border text-slate-500'
                }`}>
                  {app.status?.toUpperCase()}
                </span>
              </div>

              {/* Outcome buttons — only shown when submitted */}
              {app.status === 'submitted' && (
                <div className="mt-4 pt-4 border-t border-surface-border">
                  <p className="text-xs text-slate-500 mb-2">Record outcome:</p>
                  <div className="flex gap-2 flex-wrap">
                    {STAGES.map(s => (
                      <button
                        key={s}
                        onClick={() => recordOutcome(app.application_id, s)}
                        disabled={recording === app.application_id + s}
                        className={`text-xs px-3 py-1.5 rounded-full border font-medium transition-colors disabled:opacity-50 ${
                          s === 'offer'
                            ? 'bg-emerald-900/30 border-emerald-500/30 text-emerald-400 hover:bg-emerald-900/50'
                            : s === 'rejected'
                            ? 'bg-red-900/30 border-red-500/30 text-red-400 hover:bg-red-900/50'
                            : 'bg-surface border-surface-border text-slate-400 hover:bg-surface-hover'
                        }`}
                      >
                        {recording === app.application_id + s
                          ? <Spinner size="sm" />
                          : STAGE_LABELS[s]
                        }
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Feedback / calibration summary */}
      {feedback?.total_with_feedback > 0 && (
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

      {toast && <Toast {...toast} onClose={() => setToast(null)} />}
    </div>
  )
}
