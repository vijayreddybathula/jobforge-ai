import { useEffect, useState } from 'react'
import { useApi } from '../hooks/useApi'
import { BarChart2, ChevronDown } from 'lucide-react'
import Spinner from '../components/common/Spinner'
import Toast from '../components/common/Toast'
import EmptyState from '../components/common/EmptyState'

const STAGES = ['phone_screen', 'onsite', 'offer', 'rejected', 'no_response']
const STAGE_LABELS = { phone_screen: 'Phone Screen', onsite: 'Onsite', offer: 'Offer', rejected: 'Rejected', no_response: 'No Response' }
const STAGE_COLORS = { phone_screen: 'badge-validate', onsite: 'badge-auto', offer: 'badge-apply', rejected: 'badge-skip', no_response: 'badge-default' }

export default function ApplicationsPage() {
  const api = useApi()
  const [applications, setApplications] = useState([])
  const [loading, setLoading] = useState(true)
  const [feedback, setFeedback] = useState(null)
  const [recording, setRecording] = useState(null)
  const [toast, setToast] = useState(null)

  useEffect(() => {
    Promise.all([
      api.get('/applications/'),
      api.get('/applications/feedback/summary').catch(() => null),
    ]).then(([apps, fb]) => {
      setApplications(apps)
      setFeedback(fb)
    }).catch(e => setToast({ message: e.message, type: 'error' }))
     .finally(() => setLoading(false))
  }, [])

  const recordOutcome = async (appId, stage) => {
    setRecording(appId)
    try {
      await api.post(`/applications/${appId}/outcome`, { stage })
      setToast({ message: `Outcome recorded: ${STAGE_LABELS[stage]}` })
      // Refresh
      const apps = await api.get('/applications/')
      setApplications(apps)
    } catch (e) {
      setToast({ message: e.message, type: 'error' })
    } finally { setRecording(null) }
  }

  const STATUS_COLORS = { submitted: 'badge-apply', started: 'badge-validate', cancelled: 'badge-skip', failed: 'badge-skip' }

  return (
    <div className="max-w-3xl space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-slate-100">Applications</h1>
        <p className="text-slate-400 text-sm mt-1">Track your application outcomes and score calibration</p>
      </div>

      {loading
        ? <div className="flex justify-center py-12"><Spinner size="lg" /></div>
        : applications.length === 0
          ? <EmptyState icon={BarChart2} title="No applications yet" description="Start applying to jobs to track outcomes here." />
          : (
            <div className="space-y-3">
              {applications.map(app => (
                <div key={app.application_id} className="card">
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <p className="font-medium text-slate-200 text-sm">Job ID: {app.job_id.slice(0, 8)}...</p>
                      <p className="text-xs text-slate-500 mt-0.5">
                        {app.submitted_at ? `Submitted ${new Date(app.submitted_at).toLocaleDateString()}` : `Started ${new Date(app.created_at).toLocaleDateString()}`}
                        {' · '}{app.apply_mode}
                      </p>
                    </div>
                    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold border ${STATUS_COLORS[app.status] || 'badge-default'}`}>
                      {app.status.toUpperCase()}
                    </span>
                  </div>

                  {app.status === 'submitted' && (
                    <div className="mt-4 pt-4 border-t border-surface-border">
                      <p className="text-xs text-slate-500 mb-2">Record outcome:</p>
                      <div className="flex gap-2 flex-wrap">
                        {STAGES.map(s => (
                          <button key={s}
                            onClick={() => recordOutcome(app.application_id, s)}
                            disabled={recording === app.application_id}
                            className={`text-xs px-3 py-1.5 rounded-full border font-medium transition-colors ${
                              STAGE_COLORS[s] === 'badge-apply' ? 'bg-emerald-900/30 border-emerald-500/30 text-emerald-400 hover:bg-emerald-900/50' :
                              STAGE_COLORS[s] === 'badge-skip'  ? 'bg-red-900/30 border-red-500/30 text-red-400 hover:bg-red-900/50' :
                              'bg-surface border-surface-border text-slate-400 hover:bg-surface-hover'
                            }`}>
                            {STAGE_LABELS[s]}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )
      }

      {/* Feedback summary */}
      {feedback && feedback.total_with_feedback > 0 && (
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
          {feedback.insight && <p className="text-xs text-slate-500 mt-3 border-t border-surface-border pt-3">{feedback.insight}</p>}
        </div>
      )}

      {toast && <Toast {...toast} onClose={() => setToast(null)} />}
    </div>
  )
}
