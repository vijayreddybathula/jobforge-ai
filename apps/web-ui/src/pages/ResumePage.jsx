import { useEffect, useState, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useApi } from '../hooks/useApi'
import { useDropzone } from 'react-dropzone'
import { Upload, FileText, Trash2, ChevronRight, RefreshCw, AlertCircle } from 'lucide-react'
import Spinner from '../components/common/Spinner'
import Toast from '../components/common/Toast'

export default function ResumePage() {
  const api      = useApi()
  const navigate = useNavigate()

  const [resumes,     setResumes]     = useState([])
  const [loading,     setLoading]     = useState(true)
  const [uploading,   setUploading]   = useState(false)
  const [uploadError, setUploadError] = useState('')
  const [analyzing,   setAnalyzing]   = useState(null)
  const [toast,       setToast]       = useState(null)

  // Prevent double-load in React Strict Mode
  const didLoad = useRef(false)

  const showToast = (message, type = 'success') => setToast({ message, type })

  /* ── Load ─────────────────────────────────────────────────── */
  const loadResumes = useCallback(async () => {
    try {
      const data = await api.get('/resume/')
      setResumes(Array.isArray(data) ? data : [])
    } catch (e) {
      showToast(e.message, 'error')
    } finally {
      setLoading(false)
    }
  }, []) // api is stable — no deps needed

  useEffect(() => {
    if (didLoad.current) return
    didLoad.current = true
    loadResumes()
  }, []) // run once on mount

  /* ── Upload ────────────────────────────────────────────────── */
  const doUpload = useCallback(async (file) => {
    setUploadError('')
    setUploading(true)
    try {
      // api.upload does NOT set Content-Type (lets browser set multipart boundary)
      const result = await api.upload('/resume/upload', file)
      if (result.duplicate) {
        showToast('This exact resume is already uploaded.', 'error')
      } else {
        showToast(`Resume uploaded! v${result.version ?? ''}`)
        loadResumes()
      }
    } catch (e) {
      const msg = e.message || 'Upload failed — check file type (PDF/DOCX) and size (≤10 MB).'
      setUploadError(msg)
      showToast(msg, 'error')
    } finally {
      setUploading(false)
    }
  }, [])

  const onDrop = useCallback((accepted, rejected) => {
    if (rejected?.length) {
      const reason = rejected[0]?.errors?.[0]?.message || 'File type not supported.'
      setUploadError(`${reason} — Please use PDF or DOCX, max 10 MB.`)
      return
    }
    if (accepted?.[0]) doUpload(accepted[0])
  }, [doUpload])

  const { getRootProps, getInputProps, isDragActive, open } = useDropzone({
    onDrop,
    // Accept PDF and DOCX only. Do NOT include 'application/octet-stream' —
    // that matches everything and causes confusing "wrong file type" errors.
    accept: {
      'application/pdf': ['.pdf'],
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
    },
    maxFiles: 1,
    maxSize: 10 * 1024 * 1024,
  })

  /* ── Analyze ───────────────────────────────────────────────── */
  const handleAnalyze = async (resumeId) => {
    setAnalyzing(resumeId)
    try {
      await api.post(`/resume/analyze/${resumeId}`)
      showToast('Analysis complete!')
      navigate(`/resume/${resumeId}/roles`)
    } catch (e) {
      showToast(e.message, 'error')
    } finally {
      setAnalyzing(null)
    }
  }

  /* ── Delete ────────────────────────────────────────────────── */
  const handleDelete = async (resumeId) => {
    if (!confirm('Delete this resume? This cannot be undone.')) return
    try {
      await api.delete(`/resume/${resumeId}`)
      showToast('Resume deleted.')
      setResumes(prev => prev.filter(r => r.resume_id !== resumeId))
    } catch (e) {
      showToast(e.message, 'error')
    }
  }

  /* ── Render ────────────────────────────────────────────────── */
  return (
    <div className="max-w-3xl space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-slate-100">Resume</h1>
        <p className="text-slate-400 text-sm mt-1">Upload your resume to start the pipeline</p>
      </div>

      {/* Existing resumes */}
      {loading ? (
        <div className="flex justify-center py-12"><Spinner size="lg" /></div>
      ) : resumes.length > 0 && (
        <div className="space-y-3">
          <h2 className="text-sm font-medium text-slate-400 uppercase tracking-wider">Your Resumes</h2>
          {resumes.map(r => (
            <div key={r.resume_id} className="card flex items-center gap-4">
              <div className="w-10 h-10 rounded-lg bg-brand/15 flex items-center justify-center shrink-0">
                <FileText size={18} className="text-brand" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="font-medium text-slate-200 truncate">{r.file_name}</p>
                <p className="text-xs text-slate-500">
                  v{r.version} · {new Date(r.created_at).toLocaleDateString()}
                  {r.has_parsed_data ? ' · ✓ Analyzed' : ' · Not analyzed'}
                </p>
              </div>
              <div className="flex items-center gap-2 shrink-0 flex-wrap">
                <button
                  onClick={() => navigate(`/resume/${r.resume_id}/roles`)}
                  className="btn-secondary btn-sm flex items-center gap-1.5"
                >
                  View Roles <ChevronRight size={13} />
                </button>
                <button
                  onClick={() => handleAnalyze(r.resume_id)}
                  disabled={analyzing === r.resume_id}
                  className="btn-secondary btn-sm flex items-center gap-1.5"
                >
                  {analyzing === r.resume_id ? <Spinner size="sm" /> : <RefreshCw size={13} />}
                  {r.has_parsed_data ? 'Re-analyze' : 'Analyze'}
                </button>
                <button onClick={() => handleDelete(r.resume_id)} className="btn-danger btn-sm">
                  <Trash2 size={13} />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Upload zone */}
      <div>
        <h2 className="text-sm font-medium text-slate-400 uppercase tracking-wider mb-3">
          {resumes.length > 0 ? 'Upload New Version' : 'Upload Resume'}
        </h2>

        {uploadError && (
          <div className="mb-3 flex items-start gap-2 bg-red-950 border border-red-500/30 text-red-400 text-sm px-4 py-3 rounded-lg">
            <AlertCircle size={16} className="shrink-0 mt-0.5" />
            <span>{uploadError}</span>
          </div>
        )}

        <div
          {...getRootProps()}
          className={`border-2 border-dashed rounded-xl p-12 text-center cursor-pointer transition-colors ${
            isDragActive
              ? 'border-brand bg-brand/5'
              : 'border-surface-border hover:border-slate-600'
          }`}
        >
          <input {...getInputProps()} />
          {uploading ? (
            <div className="flex flex-col items-center gap-3">
              <Spinner size="lg" />
              <p className="text-sm text-slate-400">Uploading…</p>
            </div>
          ) : (
            <>
              <Upload size={32} className={`mx-auto mb-3 ${isDragActive ? 'text-brand' : 'text-slate-600'}`} />
              <p className="text-slate-300 font-medium mb-1">
                {isDragActive ? 'Drop it here!' : 'Drop your resume here'}
              </p>
              <p className="text-sm text-slate-500">PDF or DOCX · Max 10 MB</p>
              <button
                type="button"
                onClick={e => { e.stopPropagation(); open() }}
                className="btn-secondary btn-sm mt-4"
              >
                Browse files
              </button>
            </>
          )}
        </div>

        {resumes.length > 0 && (
          <p className="text-xs text-slate-500 mt-2 flex items-center gap-1">
            <AlertCircle size={12} />
            Uploading creates a new version. Existing applications are not affected.
          </p>
        )}
      </div>

      {toast && <Toast {...toast} onClose={() => setToast(null)} />}
    </div>
  )
}
