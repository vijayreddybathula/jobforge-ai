import { useEffect, useState } from 'react'
import { useApi } from '../hooks/useApi'
import { Save, X, Plus } from 'lucide-react'
import Spinner from '../components/common/Spinner'
import Toast from '../components/common/Toast'

const VISA_OPTIONS  = ['US_CITIZEN', 'GREENCARD', 'H1B', 'L1', 'OPT', 'OTHER']
const SIZE_OPTIONS  = ['startup', 'mid-size', 'enterprise']
// "Other" is kept as a selectable checkbox, plus a free-text field that appears when checked
const INDUSTRY_BASE = ['Tech', 'Finance', 'Healthcare', 'Retail', 'Manufacturing']

const DEFAULT_FORM = {
  visa_status:               'US_CITIZEN',
  work_authorization:        'US_CITIZEN',
  location_preferences:      { remote: true, hybrid: true, onsite: false, cities: [] },
  salary_min_usd:            100000,
  salary_max_usd:            200000,
  company_size_preferences:  [],
  industry_preferences:      [],
}

export default function PreferencesPage() {
  const api = useApi()
  const [form,      setForm]      = useState(DEFAULT_FORM)
  const [cityInput, setCityInput] = useState('')
  // "Other" industry free-text
  const [otherIndustry,    setOtherIndustry]    = useState('')
  const [otherIndustryOn,  setOtherIndustryOn]  = useState(false)
  const [exists,    setExists]    = useState(false)
  const [loading,   setLoading]   = useState(true)
  const [saving,    setSaving]    = useState(false)
  const [toast,     setToast]     = useState(null)

  /* ── load ──────────────────────────────────────────────────────── */
  useEffect(() => {
    api.get('/preferences/')
      .then(d => {
        const industries = d.industry_preferences || []
        // Detect if a previously-saved "Other:..." entry exists
        const otherEntry = industries.find(i => i.startsWith('Other:'))
        const baseInds   = industries.filter(i => !i.startsWith('Other:'))
        setForm({
          visa_status:              d.visa_status              || 'US_CITIZEN',
          work_authorization:       d.work_authorization       || 'US_CITIZEN',
          location_preferences:     d.location_preferences     || { remote: true, hybrid: true, onsite: false, cities: [] },
          salary_min_usd:           d.salary_min_usd           || 100000,
          salary_max_usd:           d.salary_max_usd           || 200000,
          company_size_preferences: d.company_size_preferences || [],
          industry_preferences:     baseInds,
        })
        if (otherEntry) {
          setOtherIndustryOn(true)
          setOtherIndustry(otherEntry.replace('Other:', '').trim())
        }
        setExists(true)
      })
      .catch(() => {}) // 404 = first time, just use defaults
      .finally(() => setLoading(false))
  }, [])

  /* ── helpers ───────────────────────────────────────────────────── */
  const set    = (k, v)  => setForm(f => ({ ...f, [k]: v }))
  const setLoc = (k, v)  => setForm(f => ({ ...f, location_preferences: { ...f.location_preferences, [k]: v } }))

  const toggleSize = (val) => setForm(f => ({
    ...f,
    company_size_preferences: f.company_size_preferences.includes(val)
      ? f.company_size_preferences.filter(x => x !== val)
      : [...f.company_size_preferences, val],
  }))

  const toggleIndustry = (val) => setForm(f => ({
    ...f,
    industry_preferences: f.industry_preferences.includes(val)
      ? f.industry_preferences.filter(x => x !== val)
      : [...f.industry_preferences, val],
  }))

  const addCity = () => {
    const city = cityInput.trim()
    if (!city) return
    const cities = form.location_preferences.cities || []
    if (cities.includes(city)) { setCityInput(''); return }
    setLoc('cities', [...cities, city])
    setCityInput('')
  }

  const removeCity = (c) =>
    setLoc('cities', (form.location_preferences.cities || []).filter(x => x !== c))

  /* ── save ──────────────────────────────────────────────────────── */
  const handleSave = async () => {
    // Merge "Other" industry free-text into the list before saving
    const industries = [...form.industry_preferences]
    if (otherIndustryOn && otherIndustry.trim()) {
      industries.push(`Other:${otherIndustry.trim()}`)
    }
    const payload = { ...form, industry_preferences: industries }

    setSaving(true)
    try {
      if (exists) {
        await api.put('/preferences/', payload)
      } else {
        await api.post('/preferences/', payload)
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

  const cities = form.location_preferences.cities || []

  return (
    <div className="max-w-2xl space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-100">Job Preferences</h1>
          <p className="text-slate-400 text-sm mt-1">Controls scoring and job matching</p>
        </div>
        <button onClick={handleSave} disabled={saving} className="btn-primary flex items-center gap-2">
          {saving ? <><Spinner size="sm" /> Saving…</> : <><Save size={15} /> Save Changes</>}
        </button>
      </div>

      {/* Work auth */}
      <div className="card space-y-4">
        <h2 className="font-semibold text-slate-200">Work Authorization</h2>
        <div>
          <label className="label">Visa / Work Status</label>
          <select className="input" value={form.visa_status} onChange={e => set('visa_status', e.target.value)}>
            {VISA_OPTIONS.map(v => <option key={v} value={v}>{v.replace(/_/g, ' ')}</option>)}
          </select>
        </div>
      </div>

      {/* Location */}
      <div className="card space-y-4">
        <h2 className="font-semibold text-slate-200">Location Preferences</h2>

        {/* Work type checkboxes */}
        <div className="flex gap-6">
          {['remote', 'hybrid', 'onsite'].map(t => (
            <label key={t} className="flex items-center gap-2 cursor-pointer select-none">
              <input
                type="checkbox" className="accent-brand w-4 h-4"
                checked={!!form.location_preferences[t]}
                onChange={e => setLoc(t, e.target.checked)}
              />
              <span className="text-sm capitalize text-slate-300">{t}</span>
            </label>
          ))}
        </div>

        {/* Cities */}
        <div>
          <label className="label">Preferred Cities</label>

          {/* Tag list */}
          {cities.length > 0 && (
            <div className="flex flex-wrap gap-2 mb-2">
              {cities.map(c => (
                <span key={c} className="flex items-center gap-1 bg-surface border border-surface-border rounded-full px-3 py-1 text-sm text-slate-300">
                  {c}
                  <button
                    type="button"
                    onClick={() => removeCity(c)}
                    className="text-slate-500 hover:text-red-400 ml-1"
                  >
                    <X size={12} />
                  </button>
                </span>
              ))}
            </div>
          )}

          {/* Input row — pressing Enter or clicking Add both work */}
          <div className="flex gap-2">
            <input
              className="input"
              placeholder="e.g. Dallas, TX"
              value={cityInput}
              onChange={e => setCityInput(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); addCity() } }}
            />
            <button
              type="button"
              onClick={addCity}
              className="btn-secondary flex items-center gap-1.5 shrink-0"
            >
              <Plus size={14} /> Add
            </button>
          </div>
        </div>
      </div>

      {/* Compensation */}
      <div className="card space-y-4">
        <h2 className="font-semibold text-slate-200">Compensation</h2>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="label">Minimum Base (USD)</label>
            <input
              type="number" className="input"
              value={form.salary_min_usd}
              onChange={e => set('salary_min_usd', Number(e.target.value))}
            />
          </div>
          <div>
            <label className="label">Maximum Base (USD)</label>
            <input
              type="number" className="input"
              value={form.salary_max_usd}
              onChange={e => set('salary_max_usd', Number(e.target.value))}
            />
          </div>
        </div>
      </div>

      {/* Company */}
      <div className="card space-y-5">
        <h2 className="font-semibold text-slate-200">Company Preferences</h2>

        {/* Size */}
        <div>
          <label className="label">Company Size</label>
          <div className="flex gap-6 flex-wrap">
            {SIZE_OPTIONS.map(s => (
              <label key={s} className="flex items-center gap-2 cursor-pointer select-none">
                <input
                  type="checkbox" className="accent-brand w-4 h-4"
                  checked={form.company_size_preferences.includes(s)}
                  onChange={() => toggleSize(s)}
                />
                <span className="text-sm capitalize text-slate-300">{s}</span>
              </label>
            ))}
          </div>
        </div>

        {/* Industries */}
        <div>
          <label className="label">Industries</label>
          <div className="flex gap-6 flex-wrap">
            {INDUSTRY_BASE.map(i => (
              <label key={i} className="flex items-center gap-2 cursor-pointer select-none">
                <input
                  type="checkbox" className="accent-brand w-4 h-4"
                  checked={form.industry_preferences.includes(i)}
                  onChange={() => toggleIndustry(i)}
                />
                <span className="text-sm text-slate-300">{i}</span>
              </label>
            ))}

            {/* Other — checkbox + inline text field */}
            <label className="flex items-center gap-2 cursor-pointer select-none">
              <input
                type="checkbox" className="accent-brand w-4 h-4"
                checked={otherIndustryOn}
                onChange={e => setOtherIndustryOn(e.target.checked)}
              />
              <span className="text-sm text-slate-300">Other</span>
            </label>
          </div>

          {/* Inline text field appears when Other is checked */}
          {otherIndustryOn && (
            <div className="mt-3">
              <input
                className="input max-w-xs"
                placeholder="Describe the industry…"
                value={otherIndustry}
                onChange={e => setOtherIndustry(e.target.value)}
                autoFocus
              />
            </div>
          )}
        </div>
      </div>

      {toast && <Toast {...toast} onClose={() => setToast(null)} />}
    </div>
  )
}
