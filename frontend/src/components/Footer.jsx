import { Activity } from 'lucide-react'

export default function Footer() {
  return (
    <footer className="mt-8 border-t border-slate-200/80 bg-white">
      <div className="max-w-7xl mx-auto px-6 py-8">
        <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
          {/* Brand */}
          <div className="flex items-center gap-2.5">
            <div className="w-6 h-6 rounded-md bg-teal-600 flex items-center justify-center">
              <Activity size={13} className="text-white" />
            </div>
            <span className="text-sm font-semibold text-slate-700">DriftNet</span>
          </div>

          {/* Disclaimer */}
          <p className="text-xs text-slate-400 text-center max-w-xl leading-relaxed">
            DriftNet is a research decision-support system trained on TCGA data.
            Predictions are probabilistic and do not replace clinical judgment or expert diagnosis.
            For research use only.
          </p>

          {/* Version */}
          <p className="text-xs text-slate-300">v1.0.0</p>
        </div>
      </div>
    </footer>
  )
}
