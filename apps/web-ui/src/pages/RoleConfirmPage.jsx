import { useEffect, useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { useApi } from '../hooks/useApi'
import { ArrowLeft, Plus, X, CheckCircle } from 'lucide-react'
import Spinner from '../components/common/Spinner'
import Toast from '../components/common/Toast'

export default function RoleConfirmPage() {
  const { id: resumeId } = useParams()
  const api = useApi()
  const navigate = useNavigate()
  const [roles, setRoles] = useState([])
  const [selected, setSelected] = useState(new Set())
  const [customRole, setCustomRole] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [toast, setToast] = useState(null)

  useEffect(() => {
    api.get(`/resume/roles/${resumeId}`)
      .then(d => {
        setRoles(d.roles || [])
        setSelected(new Set(d.roles.filter(r => r.is_confirmed).map(r => r.role_title)))
      })
      .catch(e => setToast({ message: e.message, type: 'error' }))
      .finally(() => setLoading(false))
  }, [resumeId])

  const toggle = (title) => setSelected(prev => {
    const n = new Set(prev)
    n.has(title) ? n.delete(title) : n.add(title)
    return n
  })

  const addCustom = () => {
    if (!customRole.trim()) return
    setRoles(prev => [...prev, { role_title: customRole.trim(), confidence_score: null, is_confirmed: false, custom: true }])
    setSelected(prev => new Set([...prev, customRole.trim()]))
    setCustomRole('')
  }

  const handleSave = async () => {
    if (selected.size === 0) { setToast({ message: 'Select at least one role.', type: 'error' }); return }
    setSaving(true)
    try {
      await api.post('/resume/roles/confirm', { resume_id: resumeId, confirmed_roles: [...selected] })
      await api.post(`/profile/build-from-resume/${resumeId}`)
      setToast({ message: 'Roles confirmed and profile built!' })
      setTimeout(() => navigate('/preferences'), 1200)
    } catch (e) {
      setToast({ message: e.message, type: 'error' })
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="max-w-2xl space-y-6">
      <Link to="/resume" className="inline-flex items-center gap-1.5 text-sm text-slate-400 hover:text-slate-200">
        <ArrowLeft size={15} /> Back to Resume
      </Link>

      <div>
        <h1 className="text-2xl font-bold text-slate-100">Confirm Target Roles</h1>
        <p className="text-slate-400 text-sm mt-1">Select all roles you want to target. This shapes your scoring and artifacts.</p>
      </div>

      {loading
        ? <div className="flex justify-center py-12"><Spinner size="lg" /></div>
        : (
          <div className="space-y-3">
            {roles.map(r => {
              const isSelected = selected.has(r.role_title)
              return (
                <button
                  key={r.role_title}
                  onClick={() => toggle(r.role_title)}
                  className={`w-full text-left card flex items-center gap-4 transition-all ${
                    isSelected ? 'border-brand bg-brand/5' : 'hover:border-slate-600'
                  }`}
                >
                  <div className={`w-5 h-5 rounded border-2 flex items-center justify-center shrink-0 transition-colors ${
                    isSelected ? 'border-brand bg-brand' : 'border-slate-600'
                  }`}>
                    {isSelected && <CheckCircle size={12} className="text-white" />}
                  </div>
                  <div className="flex-1">
                    <p className="font-medium text-slate-200">{r.role_title}</p>
                    {r.confidence_score && (
                      <p className="text-xs text-slate-500 mt-0.5">Confidence: {r.confidence_score}%</p>
                    )}
                  </div>
                  {isSelected && <CheckCircle size={18} className="text-brand shrink-0" />}
                </button>
              )
            })}

            {/* Add custom role */}
            <div className="card">
              <p className="text-sm text-slate-400 mb-3">Add a custom role</p>
              <div className="flex gap-2">
                <input
                  className="input"
                  placeholder="e.g. Staff AI Engineer"
                  value={customRole}
                  onChange={e => setCustomRole(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && addCustom()}
                />
                <button onClick={addCustom} className="btn-secondary flex items-center gap-1.5 shrink-0">
                  <Plus size={15} /> Add
                </button>
              </div>
            </div>
          </div>
        )
      }

      <div className="flex items-center justify-between pt-2">
        <p className="text-sm text-slate-500">{selected.size} role{selected.size !== 1 ? 's' : ''} selected</p>
        <button onClick={handleSave} disabled={saving || selected.size === 0} className="btn-primary flex items-center gap-2">
          {saving ? <><Spinner size="sm" /> Saving...</> : 'Save & Build Profile →'}
        </button>
      </div>

      {toast && <Toast {...toast} onClose={() => setToast(null)} />}
    </div>
  )
}
