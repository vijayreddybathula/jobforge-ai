function color(s) {
  if (!s) return { text: 'text-slate-500', ring: 'border-slate-700', bg: 'bg-surface' }
  if (s >= 85) return { text: 'text-brand',    ring: 'border-brand/50',    bg: 'bg-brand/10' }
  if (s >= 75) return { text: 'text-emerald-400', ring: 'border-emerald-500/50', bg: 'bg-emerald-900/20' }
  if (s >= 65) return { text: 'text-amber-400',  ring: 'border-amber-500/50',  bg: 'bg-amber-900/20' }
  return          { text: 'text-red-400',    ring: 'border-red-500/50',    bg: 'bg-red-900/20' }
}

export default function ScoreCircle({ score, size = 'md' }) {
  const c = color(score)
  const dim = size === 'lg' ? 'w-16 h-16 text-xl' : 'w-12 h-12 text-base'
  return (
    <div className={`${dim} rounded-full border-2 flex items-center justify-center font-bold shrink-0 ${c.text} ${c.ring} ${c.bg}`}>
      {score ?? '—'}
    </div>
  )
}
