import { useEffect, useState } from 'react'
import { useApi } from '../hooks/useApi'
import { Save } from 'lucide-react'
import Spinner from '../components/common/Spinner'
import Toast from '../components/common/Toast'

const VISA_OPTIONS = ['US_CITIZEN', 'GREENCARD', 'H1B', 'L1', 'OPT', 'OTHER']
const SIZE_OPTIONS = ['startup', 'mid-size', 'enterprise']
const INDUSTRY_OPTIONS = ['Tech', 'Finance', 'Healthcare', 'Retail', 'Manufacturing', 'Other']

export default function PreferencesPage() {
  const api = useApi()
  const [form, setForm] = useState({
    visa_status: 'US_CITIZEN',
    work_authorization: 'US_CITIZEN',
    location_preferences: { remote: true, hybrid: true, onsite: false, cities: [] },
    salary_min_usd: 100000,
    salary_max_usd: 200000,
    company_size_preferences: ['startup', 'mid-size'],
    industry_preferences: ['Tech'],
  })
  const [cityInput, setCityInput] = useState('')
  const [exists, setExists] = useState(false)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [toast, setToast] = useState(null)

  useEffect(() => {
    api.get('/preferences/')
      .then(d => {
        setForm({
          visa_status: d.visa_status || 'US_CITIZEN',
          work_authorization: d.work_authorization || 'US_CITIZEN',
          location_preferences: d.location_preferences || { remote: true, hybrid: true, onsite: false, cities: [] },
          salary_min_usd: d.salary_min_usd || 100000,
          salary_max_usd: d.salary_max_usd || 200000,
          company_size_preferences: d.company_size_preferences || [],
          industry_preferences: d.industry_preferences || [],
        })
        setExists(true)
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }))
  const setLoc = (k, v) => setForm(f => ({ ...f, location_preferences: { ...f.location_preferences, [k]: v } }))

  const toggleArr = (key, val) => setForm(f => ({
    ...f, [key]: f[key].includes(val) ? f[key].filter(x => x !== val) : [...f[key], val]
  }))

  const addCity = () => {
    if (!cityInput.trim()) return
    setLoc('cities', [...(form.location_preferences.cities || []), cityInput.trim()])
    setCityInput('')
  }

  const removeCity = (c) => setLoc('cities', form.location_preferences.cities.filter(x => x !== c))

  const handleSave = async () => {
    setSaving(true)
    try {
      if (exists) {
        await api.put('/preferences/', form)
      } else {
        await api.post('/preferences/', form)
        setExists(true)
      }
      setToast({ message: 'Preferences saved!' })
    } catch (e) {
      setToast({ message: e.message, type: 'error' })
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <div className="flex justify-center py-20"><Spinner size="lg" /></div>

  return (
    <div className="max-w-2xl space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-100">Job Preferences</h1>
          <p className="text-slate-400 text-sm mt-1">These settings control scoring and job matching</p>
        </div>
        <button onClick={handleSave} disabled={saving} className="btn-primary flex items-center gap-2">
          {saving ? <><Spinner size="sm" /> Saving...</> : <><Save size={15} /> Save Changes</>}
        </button>
      </div>

      {/* Work auth */}
      <div className="card space-y-4">
        <h2 className="font-semibold text-slate-200">Work Authorization</h2>
        <div>
          <label className="label">Visa / Work Status</label>
          <select className="input" value={form.visa_status} onChange={e => set('visa_status', e.target.value)}>
            {VISA_OPTIONS.map(v => <option key={v} value={v}>{v.replace('_', ' ')}</option>)}
          </select>
        </div>
      </div>

      {/* Location */}
      <div className="card space-y-4">
        <h2 className="font-semibold text-slate-200">Location Preferences</h2>
        <div className="flex gap-4">
          {['remote', 'hybrid', 'onsite'].map(t => (
            <label key={t} className="flex items-center gap-2 cursor-pointer">
              <input type="checkbox" className="accent-brand"
                checked={!!form.location_preferences[t]}
                onChange={e => setLoc(t, e.target.checked)}
              />
              <span className="text-sm capitalize text-slate-300">{t}</span>
            </label>
          ))}
        </div>
        <div>
          <label className="label">Preferred Cities</label>
          <div className="flex flex-wrap gap-2 mb-2">
            {(form.location_preferences.cities || []).map(c => (
              <span key={c} className="flex items-center gap-1 bg-surface border border-surface-border rounded-full px-3 py-1 text-sm text-slate-300">
                {c}
                <button onClick={() => removeCity(c)} className="text-slate-500 hover:text-red-400"><X size={12} /></button>
              </span>
            ))}
          </div>
          <div className="flex gap-2">
            <input className="input" placeholder="e.g. Dallas, TX" value={cityInput} onChange={e => setCityInput(e.target.value)} onKeyDown={e => e.key === 'Enter' && addCity()} />
            <button onClick={addCity} className="btn-secondary shrink-0">+ Add</button>
          </div>
        </div>
      </div>

      {/* Compensation */}
      <div className="card space-y-4">
        <h2 className="font-semibold text-slate-200">Compensation</h2>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="label">Minimum Base (USD)</label>
            <input type="number" className="input" value={form.salary_min_usd} onChange={e => set('salary_min_usd', +e.target.value)} />
          </div>
          <div>
            <label className="label">Maximum Base (USD)</label>
            <input type="number" className="input" value={form.salary_max_usd} onChange={e => set('salary_max_usd', +e.target.value)} />
          </div>
        </div>
      </div>

      {/* Company */}
      <div className="card space-y-4">
        <h2 className="font-semibold text-slate-200">Company Preferences</h2>
        <div>
          <label className="label">Company Size</label>
          <div className="flex gap-4 flex-wrap">
            {SIZE_OPTIONS.map(s => (
              <label key={s} className="flex items-center gap-2 cursor-pointer">
                <input type="checkbox" className="accent-brand"
                  checked={form.company_size_preferences.includes(s)}
                  onChange={() => toggleArr('company_size_preferences', s)}
                />
                <span className="text-sm capitalize text-slate-300">{s}</span>
              </label>
            ))}
          </div>
        </div>
        <div>
          <label className="label">Industries</label>
          <div className="flex gap-4 flex-wrap">
            {INDUSTRY_OPTIONS.map(i => (
              <label key={i} className="flex items-center gap-2 cursor-pointer">
                <input type="checkbox" className="accent-brand"
                  checked={form.industry_preferences.includes(i)}
                  onChange={() => toggleArr('industry_preferences', i)}
                />
                <span className="text-sm text-slate-300">{i}</span>
              </label>
            ))}
          </div>
        </div>
      </div>

      {toast && <Toast {...toast} onClose={() => setToast(null)} />}
    </div>
  )
}
