/**
 * Spinner uses hard-coded Tailwind colour classes that don't rely on custom
 * design tokens, so it always renders visibly regardless of tailwind.config.js.
 * The border colours map to standard slate/indigo palette.
 */
export default function Spinner({ size = 'md', className = '' }) {
  const s =
    size === 'sm' ? 'w-4 h-4 border-2'
    : size === 'lg' ? 'w-8 h-8 border-2'
    : 'w-5 h-5 border-2'
  return (
    <div className={`${s} border-slate-600 border-t-indigo-400 rounded-full animate-spin ${className}`} />
  )
}
