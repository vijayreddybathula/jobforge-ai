export default function Spinner({ size = 'md', className = '' }) {
  const s = size === 'sm' ? 'w-4 h-4 border-2' : size === 'lg' ? 'w-8 h-8 border-2' : 'w-5 h-5 border-2'
  return (
    <div className={`${s} border-surface-border border-t-brand rounded-full animate-spin ${className}`} />
  )
}
