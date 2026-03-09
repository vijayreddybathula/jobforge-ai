import { useEffect, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useApi } from '../hooks/useApi'
import { useDropzone } from 'react-dropzone'
import { Upload, FileText, Trash2, ChevronRight, RefreshCw, AlertCircle } from 'lucide-react'
import Spinner from '../components/common/Spinner'
import Toast from '../components/common/Toast'

export default function ResumePage() {
  const api      = useApi()
  const navigate = useNavigate()
  const [resumes,   setResumes]   = useState([])
  const [loading,   setLoading]   = useState(true)
  const [uploading, setUploading] = useState(false)
  const [analyzing, setAnalyzing] = useState(null)
  const [toast,     setToast]     = useState(null)

  const showToast = (message, type = 'success') => setToast({ message, type })

  /* ── load list ─────────────────────────────────────────────────── */
  const loadResumes = useCallback(async () => {
    try {
      const data = await api.get('/resume/')
      setResumes(Array.isArray(data) ? data : [])
    } catch (e) {
      showToast(e.message, 'error')
    } finally {
      setLoading(false)
    }
  }, [api])

  useEffect(() => { loadResumes() }, [loadResumes])

  /* ── upload ─────────────────────────────────────────────────────── */
  const onDrop = useCallback(async (accepted, rejected) => {
    // Show a clear message if the file type was rejected by the dropzone
    if (rejected?.length) {
      showToast('Only PDF or DOCX files are accepted.', 'error')
      return
    }
    const file = accepted[0]
    if (!file) return

    // Client-side size guard (10 MB)
    if (file.size > 10 * 1024 * 1024) {
      showToast('File is too large. Max 10 MB.', 'error')
      return
    }

    setUploading(true)
    try {
      const result = await api.upload('/resume/upload', file)
      if (result.duplicate) {
        showToast('This resume is already uploaded (identical content).', 'error')
      } else {
        showToast('Resume uploaded! Click Analyze to extract roles.')
      }
      await loadResumes()
    } catch (e) {
      // Surface the exact server error message
      showToast(e.message || 'Upload failed. Is the API running?', 'error')
    } finally {
      setUploading(false)
    }
  }, [api, loadResumes])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    // Accept both MIME types and extensions so macOS + Windows both work
    accept: {
      'application/pdf': ['.pdf'],
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
      'application/msword': ['.doc'],
    },
    maxFiles: 1,
    // Disable the built-in size check — we handle it ourselves above
    // so we can show a nicer message
    maxSize: undefined,
  })

  /* ── analyze ─────────────────────────────────────────────────── */
  const handleAnalyze = async (resumeId) => {
    setAnalyzing(resumeId)
    try {
      await api.post(`/resume/analyze/${resumeId}`)
      showToast('Analysis complete! Confirm your target roles.')
      navigate(`/resume/${resumeId}/roles`)
    } catch (e) {
      showToast(e.message, 'error')
    } finally {
      setAnalyzing(null)
    }
  }

  /* ── delete ─────────────────────────────────────────────────── */
  const handleDelete = async (resumeId) => {
    if (!confirm('Delete this resume? This cannot be undone.')) return
    try {
      await api.delete(`/resume/${resumeId}`)
      showToast('Resume deleted.')
      await loadResumes()
    } catch (e) {
      showToast(e.message, 'error')
    }
  }

  /* ── render ─────────────────────────────────────────────────── */
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
              <div className="flex items-center gap-2 shrink-0">
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

        <div
          {...getRootProps()}
          className={`border-2 border-dashed rounded-xl p-12 text-center cursor-pointer transition-colors ${
            isDragActive ? 'border-brand bg-brand/5' : 'border-surface-border hover:border-slate-600'
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
              <button type="button" className="btn-secondary btn-sm mt-4">Browse files</button>
            </>
          )}
        </div>

        {resumes.length > 0 && (
          <p className="text-xs text-slate-500 mt-2 flex items-center gap-1">
            <AlertCircle size={12} />
            Uploading a new file creates a new version. Existing applications are not affected.
          </p>
        )}
      </div>

      {toast && <Toast {...toast} onClose={() => setToast(null)} />}
    </div>
  )
}
