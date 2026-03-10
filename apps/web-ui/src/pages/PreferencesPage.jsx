import { useEffect, useState } from 'react'
import { useApi } from '../hooks/useApi'
import { Save, Plus, X } from 'lucide-react'
import Spinner from '../components/common/Spinner'
import Toast from '../components/common/Toast'

const VISA_OPTIONS    = ['US_CITIZEN', 'GREENCARD', 'H1B', 'L1', 'OPT', 'OTHER']
const SIZE_OPTIONS    = ['startup', 'mid-size', 'enterprise']
const BASE_INDUSTRIES = ['Tech', 'Finance', 'Healthcare', 'Retail', 'Manufacturing']

const DEFAULT_FORM = {
  visa_status: 'US_CITIZEN',
  work_authorization: 'US_CITIZEN',
  location_preferences: { remote: true, hybrid: true, onsite: false, cities: [] },
  salary_min_usd: 100000,
  salary_max_usd: 200000,
  company_size_preferences: ['startup', 'mid-size'],
  industry_preferences: ['Tech'],
}

export default function PreferencesPage() {
  const api = useApi()

  const [form,       setForm]       = useState(DEFAULT_FORM)
  const [cityInput,  setCityInput]  = useState('')
  const [otherIndustry, setOtherIndustry] = useState('')   // free-text "Other" industry
  const [exists,     setExists]     = useState(false)
  const [loading,    setLoading]    = useState(true)
  const [saving,     setSaving]     = useState(false)
  const [toast,      setToast]      = useState(null)

  /* ── Load existing prefs ───────────────────────────────────── */
  useEffect(() => {
    api.get('/preferences/')
      .then(d => {
        // Restore any custom "Other" industries already saved
        const savedIndustries = d.industry_preferences || []
        const customOnes = savedIndustries.filter(i => !BASE_INDUSTRIES.includes(i))

        setForm({
          visa_status:              d.visa_status              || 'US_CITIZEN',
          work_authorization:       d.work_authorization       || 'US_CITIZEN',
          location_preferences:     d.location_preferences     || DEFAULT_FORM.location_preferences,
          salary_min_usd:           d.salary_min_usd           ?? 100000,
          salary_max_usd:           d.salary_max_usd           ?? 200000,
          company_size_preferences: d.company_size_preferences || [],
          industry_preferences:     savedIndustries,
        })
        if (customOnes.length) setOtherIndustry(customOnes.join(', '))
        setExists(true)
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  /* ── Helpers ───────────────────────────────────────────────── */
  const set    = (k, v) => setForm(f => ({ ...f, [k]: v }))
  const setLoc = (k, v) => setForm(f => ({
    ...f,
    location_preferences: { ...f.location_preferences, [k]: v },
  }))

  const toggleSize = (val) => setForm(f => ({
    ...f,
    company_size_preferences: f.company_size_preferences.includes(val)
      ? f.company_size_preferences.filter(x => x !== val)
      : [...f.company_size_preferences, val],
  }))

  const toggleBaseIndustry = (val) => setForm(f => ({
    ...f,
    industry_preferences: f.industry_preferences.includes(val)
      ? f.industry_preferences.filter(x => x !== val)
      : [...f.industry_preferences, val],
  }))

  /* ── City helpers ──────────────────────────────────────────── */
  const addCity = () => {
    const city = cityInput.trim()
    if (!city) return
    const current = form.location_preferences.cities || []
    if (current.includes(city)) { setCityInput(''); return }
    setLoc('cities', [...current, city])
    setCityInput('')
  }
  const removeCity = (c) =>
    setLoc('cities', (form.location_preferences.cities || []).filter(x => x !== c))

  /* ── Other industry helpers ────────────────────────────────── */
  const commitOtherIndustry = () => {
    // Parse comma-separated entries, strip blanks, merge into industry_preferences
    const extras = otherIndustry
      .split(',')
      .map(s => s.trim())
      .filter(Boolean)
      .filter(s => !BASE_INDUSTRIES.includes(s))

    setForm(f => {
      const base    = f.industry_preferences.filter(i => BASE_INDUSTRIES.includes(i))
      const unique  = [...new Set([...base, ...extras])]
      return { ...f, industry_preferences: unique }
    })
  }

  /* ── Save ──────────────────────────────────────────────────── */
  const handleSave = async () => {
    // Merge any uncommitted "Other" text before saving
    const extras = otherIndustry
      .split(',')
      .map(s => s.trim())
      .filter(Boolean)
    const mergedIndustries = [
      ...new Set([
        ...form.industry_preferences.filter(i => BASE_INDUSTRIES.includes(i)),
        ...extras,
      ]),
    ]
    const payload = { ...form, industry_preferences: mergedIndustries }

    setSaving(true)
    try {
      if (exists) {
        await api.put('/preferences/', payload)
      } else {
        await api.post('/preferences/', payload)
        setExists(true)
      }
      setForm(f => ({ ...f, industry_preferences: mergedIndustries }))
      setToast({ message: 'Preferences saved!' })
    } catch (e) {
      setToast({ message: e.message, type: 'error' })
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <div className="flex justify-center py-20"><Spinner size="lg" /></div>

  const cities = form.location_preferences.cities || []
  // Determine whether any custom (non-BASE) industries are present
  const hasOtherSelected = form.industry_preferences.some(i => !BASE_INDUSTRIES.includes(i))

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

        <div className="flex gap-6">
          {['remote', 'hybrid', 'onsite'].map(t => (
            <label key={t} className="flex items-center gap-2 cursor-pointer">
              <input type="checkbox" className="accent-brand w-4 h-4"
                checked={!!form.location_preferences[t]}
                onChange={e => setLoc(t, e.target.checked)}
              />
              <span className="text-sm capitalize text-slate-300">{t}</span>
            </label>
          ))}
        </div>

        {/* ── City chips ─────────────────────────────────────── */}
        <div>
          <label className="label">Preferred Cities</label>

          {/* Existing city chips */}
          {cities.length > 0 && (
            <div className="flex flex-wrap gap-2 mb-2">
              {cities.map(c => (
                <span key={c}
                  className="inline-flex items-center gap-1 bg-surface border border-surface-border rounded-full px-3 py-1 text-sm text-slate-300">
                  {c}
                  <button
                    type="button"
                    onClick={() => removeCity(c)}
                    className="ml-1 text-slate-500 hover:text-red-400 leading-none"
                  >×</button>
                </span>
              ))}
            </div>
          )}

          {/* Input row — controlled, with explicit Add button */}
          <div className="flex gap-2">
            <input
              type="text"
              className="input"
              placeholder="e.g. Dallas, TX"
              value={cityInput}
              onChange={e => setCityInput(e.target.value)}
              onKeyDown={e => {
                if (e.key === 'Enter') { e.preventDefault(); addCity() }
              }}
            />
            <button
              type="button"
              onClick={addCity}
              className="btn-secondary shrink-0 flex items-center gap-1"
            >
              <Plus size={14} /> Add
            </button>
          </div>
          <p className="text-xs text-slate-600 mt-1">Press Enter or click Add.</p>
        </div>
      </div>

      {/* Compensation */}
      <div className="card space-y-4">
        <h2 className="font-semibold text-slate-200">Compensation</h2>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="label">Minimum Base (USD)</label>
            <input type="number" className="input"
              value={form.salary_min_usd}
              onChange={e => set('salary_min_usd', Number(e.target.value))}
            />
          </div>
          <div>
            <label className="label">Maximum Base (USD)</label>
            <input type="number" className="input"
              value={form.salary_max_usd}
              onChange={e => set('salary_max_usd', Number(e.target.value))}
            />
          </div>
        </div>
      </div>

      {/* Company preferences */}
      <div className="card space-y-5">
        <h2 className="font-semibold text-slate-200">Company Preferences</h2>

        {/* Size */}
        <div>
          <label className="label">Company Size</label>
          <div className="flex gap-6 flex-wrap">
            {SIZE_OPTIONS.map(s => (
              <label key={s} className="flex items-center gap-2 cursor-pointer">
                <input type="checkbox" className="accent-brand w-4 h-4"
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
          <div className="flex gap-6 flex-wrap mb-3">
            {BASE_INDUSTRIES.map(ind => (
              <label key={ind} className="flex items-center gap-2 cursor-pointer">
                <input type="checkbox" className="accent-brand w-4 h-4"
                  checked={form.industry_preferences.includes(ind)}
                  onChange={() => toggleBaseIndustry(ind)}
                />
                <span className="text-sm text-slate-300">{ind}</span>
              </label>
            ))}
          </div>

          {/* Other — free-text field */}
          <div>
            <label className="label">Other Industries (comma-separated)</label>
            <div className="flex gap-2">
              <input
                type="text"
                className="input"
                placeholder="e.g. Logistics, Energy, EdTech"
                value={otherIndustry}
                onChange={e => setOtherIndustry(e.target.value)}
                onBlur={commitOtherIndustry}
                onKeyDown={e => {
                  if (e.key === 'Enter') { e.preventDefault(); commitOtherIndustry() }
                }}
              />
              <button type="button" onClick={commitOtherIndustry}
                className="btn-secondary shrink-0 flex items-center gap-1">
                <Plus size={14} /> Add
              </button>
            </div>

            {/* Show custom industry chips */}
            {hasOtherSelected && (
              <div className="flex flex-wrap gap-2 mt-2">
                {form.industry_preferences
                  .filter(i => !BASE_INDUSTRIES.includes(i))
                  .map(i => (
                    <span key={i}
                      className="inline-flex items-center gap-1 bg-surface border border-surface-border rounded-full px-3 py-1 text-sm text-slate-300">
                      {i}
                      <button
                        type="button"
                        onClick={() => setForm(f => ({
                          ...f,
                          industry_preferences: f.industry_preferences.filter(x => x !== i),
                        }))}
                        className="ml-1 text-slate-500 hover:text-red-400 leading-none"
                      >×</button>
                    </span>
                  ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {toast && <Toast {...toast} onClose={() => setToast(null)} />}
    </div>
  )
}
