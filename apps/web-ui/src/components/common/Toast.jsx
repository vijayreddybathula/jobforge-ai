import { useEffect } from 'react'
import { CheckCircle, XCircle, X } from 'lucide-react'

export default function Toast({ message, type = 'success', onClose }) {
  useEffect(() => {
    const t = setTimeout(onClose, 4000)
    return () => clearTimeout(t)
  }, [onClose])

  return (
    <div className={`fixed bottom-6 right-6 z-50 flex items-center gap-3 px-4 py-3 rounded-xl border shadow-xl text-sm font-medium animate-in slide-in-from-bottom-2 ${
      type === 'success'
        ? 'bg-emerald-950 border-emerald-500/40 text-emerald-300'
        : 'bg-red-950 border-red-500/40 text-red-300'
    }`}>
      {type === 'success' ? <CheckCircle size={16} /> : <XCircle size={16} />}
      <span>{message}</span>
      <button onClick={onClose} className="ml-2 opacity-60 hover:opacity-100">
        <X size={14} />
      </button>
    </div>
  )
}
