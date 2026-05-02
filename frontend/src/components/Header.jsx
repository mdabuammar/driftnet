import { Activity } from 'lucide-react'

export default function Header() {
  return (
    <header className="sticky top-0 z-50 bg-white/90 backdrop-blur-sm border-b border-slate-200/80">
      <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
        {/* Brand */}
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-teal-600 flex items-center justify-center shadow-sm">
            <Activity className="w-4.5 h-4.5 text-white" size={18} />
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-lg font-bold text-slate-900 tracking-tight">DriftNet</span>
            <span className="hidden sm:block text-xs font-medium text-slate-400 border border-slate-200 rounded-full px-2 py-0.5">
              Research Preview
            </span>
          </div>
        </div>

        {/* Right nav */}
        <div className="flex items-center gap-4">
          <span className="hidden md:flex items-center gap-1.5 text-xs text-slate-500">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
            Backend connected
          </span>
          <a
            href="http://localhost:8000/docs"
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs font-medium text-slate-500 hover:text-teal-600 transition-colors"
          >
            API Docs
          </a>
        </div>
      </div>
    </header>
  )
}
