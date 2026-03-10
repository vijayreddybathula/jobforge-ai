import { Component } from 'react'
import { AlertCircle, RefreshCw } from 'lucide-react'

/**
 * Catches any render-time error in child components and shows a
 * friendly error card instead of a blank screen.
 *
 * Usage:
 *   <ErrorBoundary>
 *     <SomeComponent />
 *   </ErrorBoundary>
 */
export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { error: null }
  }

  static getDerivedStateFromError(error) {
    return { error }
  }

  componentDidCatch(error, info) {
    console.error('[ErrorBoundary]', error, info.componentStack)
  }

  render() {
    if (!this.state.error) return this.props.children

    const msg = this.state.error?.message || String(this.state.error)

    return (
      <div className="flex flex-col items-center justify-center min-h-[40vh] px-6">
        <div className="card max-w-lg w-full">
          <div className="flex items-start gap-3">
            <AlertCircle size={20} className="text-red-400 shrink-0 mt-0.5" />
            <div className="flex-1 min-w-0">
              <p className="text-slate-200 font-semibold">Something went wrong</p>
              <p className="text-slate-400 text-sm mt-1 break-words">{msg}</p>
            </div>
          </div>
          <button
            onClick={() => {
              this.setState({ error: null })
              window.location.reload()
            }}
            className="btn-secondary mt-4 flex items-center gap-2"
          >
            <RefreshCw size={14} /> Reload page
          </button>
        </div>
      </div>
    )
  }
}
