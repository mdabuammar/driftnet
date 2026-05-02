import { motion, AnimatePresence } from 'framer-motion'
import { RotateCcw, AlertTriangle, TrendingUp, Activity } from 'lucide-react'

// ── helpers ────────────────────────────────────────────────────────────────

const STAGE_CONFIG = {
  'Stage I':   { color: 'emerald', label: 'Stage I',   short: 'I'   },
  'Stage II':  { color: 'amber',   label: 'Stage II',  short: 'II'  },
  'Stage III': { color: 'rose',    label: 'Stage III', short: 'III' },
}

const CONFIDENCE_CONFIG = {
  high:   { label: 'High Confidence',   bg: 'bg-emerald-100', text: 'text-emerald-700', dot: 'bg-emerald-500' },
  medium: { label: 'Moderate Confidence', bg: 'bg-amber-100',  text: 'text-amber-700',   dot: 'bg-amber-500'   },
  low:    { label: 'Low Confidence',    bg: 'bg-red-100',     text: 'text-red-700',     dot: 'bg-red-500'     },
}

const BAR_COLORS = {
  'Stage I':   'bg-emerald-500',
  'Stage II':  'bg-amber-400',
  'Stage III': 'bg-rose-500',
}

const BORDER_COLORS = {
  'Stage I':   'border-emerald-200',
  'Stage II':  'border-amber-200',
  'Stage III': 'border-rose-200',
}

const BADGE_STYLES = {
  'Stage I':   'bg-emerald-50 text-emerald-800 border-emerald-200',
  'Stage II':  'bg-amber-50  text-amber-800  border-amber-200',
  'Stage III': 'bg-rose-50   text-rose-800   border-rose-200',
}

function ProbabilityBar({ stage, probability, isWinner }) {
  const pct = Math.round(probability * 100)
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className={`text-xs font-semibold ${isWinner ? 'text-slate-900' : 'text-slate-500'}`}>
            {stage}
          </span>
          {isWinner && (
            <span className="text-xs bg-slate-900 text-white px-1.5 py-0.5 rounded-full font-medium">
              Predicted
            </span>
          )}
        </div>
        <span className={`text-sm font-bold tabular-nums ${isWinner ? 'text-slate-900' : 'text-slate-400'}`}>
          {pct}%
        </span>
      </div>
      <div className="h-2 rounded-full bg-slate-100 overflow-hidden">
        <motion.div
          className={`h-full rounded-full ${BAR_COLORS[stage] ?? 'bg-teal-500'}`}
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.8, ease: [0.4, 0, 0.2, 1], delay: 0.2 }}
        />
      </div>
    </div>
  )
}

// ── ResultPanel ─────────────────────────────────────────────────────────────

export default function ResultPanel({ result, onReset }) {
  const {
    predicted_stage,
    confidence,
    confidence_level,
    probabilities,
    warning,
    cpg_count,
    latent_shape,
    embedding_shape,
    request_id,
  } = result

  const conf   = CONFIDENCE_CONFIG[confidence_level] ?? CONFIDENCE_CONFIG.low
  const border = BORDER_COLORS[predicted_stage]      ?? 'border-slate-200'
  const badge  = BADGE_STYLES[predicted_stage]        ?? ''

  const sortedProbs = probabilities
    ? Object.entries(probabilities).sort((a, b) => b[1] - a[1])
    : []

  return (
    <AnimatePresence>
      <motion.section
        initial={{ opacity: 0, y: 24 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: 24 }}
        transition={{ duration: 0.5, ease: [0.4, 0, 0.2, 1] }}
        className="max-w-7xl mx-auto px-6 pb-16"
        id="result"
      >
        {/* ── Low-confidence warning ── */}
        {warning && (
          <motion.div
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
            className="mb-4 flex items-start gap-3 bg-amber-50 border border-amber-200 rounded-xl p-4"
          >
            <AlertTriangle size={16} className="text-amber-500 mt-0.5 shrink-0" />
            <div>
              <p className="text-sm font-semibold text-amber-800">Prediction Uncertainty</p>
              <p className="text-sm text-amber-700 mt-0.5">{warning}</p>
            </div>
          </motion.div>
        )}

        {/* ── Main result card ── */}
        <div className={`card border-2 ${border} overflow-hidden`}>

          {/* Top strip */}
          <div className="bg-gradient-to-r from-slate-900 to-slate-800 px-8 py-6 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
            <div className="flex items-center gap-4">
              {/* Stage icon */}
              <div className="w-12 h-12 rounded-xl bg-white/10 flex items-center justify-center backdrop-blur-sm">
                <Activity size={22} className="text-white" />
              </div>
              <div>
                <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">
                  DriftNet Prediction
                </p>
                <div className="flex items-center gap-3">
                  <span className={`text-3xl font-bold text-white tracking-tight`}>
                    {predicted_stage ?? '—'}
                  </span>
                  <span className={`text-xs font-semibold px-2.5 py-1 rounded-full border ${badge}`}>
                    {STAGE_CONFIG[predicted_stage]?.label ?? predicted_stage}
                  </span>
                </div>
              </div>
            </div>

            {/* Confidence badge */}
            <div className={`flex items-center gap-2 px-3.5 py-2 rounded-xl border ${conf.bg} ${conf.text}`}>
              <span className={`w-2 h-2 rounded-full ${conf.dot}`} />
              <div>
                <p className={`text-xs font-semibold ${conf.text}`}>{conf.label}</p>
                <p className={`text-lg font-bold ${conf.text} leading-none`}>
                  {Math.round((confidence ?? 0) * 100)}%
                </p>
              </div>
            </div>
          </div>

          {/* Body */}
          <div className="p-8 grid grid-cols-1 lg:grid-cols-2 gap-8">

            {/* Probability distribution */}
            <div>
              <div className="flex items-center gap-2 mb-5">
                <TrendingUp size={15} className="text-teal-600" />
                <h3 className="text-sm font-semibold text-slate-700">Stage Probabilities</h3>
              </div>
              <div className="space-y-4">
                {sortedProbs.map(([stage, prob]) => (
                  <ProbabilityBar
                    key={stage}
                    stage={stage}
                    probability={prob}
                    isWinner={stage === predicted_stage}
                  />
                ))}
              </div>
            </div>

            {/* Inference details */}
            <div>
              <div className="flex items-center gap-2 mb-5">
                <Activity size={15} className="text-teal-600" />
                <h3 className="text-sm font-semibold text-slate-700">Inference Details</h3>
              </div>
              <dl className="space-y-3">
                {[
                  { label: 'CpG Probes Detected', value: cpg_count?.toLocaleString() ?? '—' },
                  { label: 'Latent Shape',         value: latent_shape ? `[${latent_shape.join(', ')}]` : '—' },
                  { label: 'Embedding Shape',      value: embedding_shape ? `[${embedding_shape.join(', ')}]` : '—' },
                  { label: 'Confidence Level',     value: confidence_level ?? '—' },
                  { label: 'Raw Confidence',       value: confidence != null ? confidence.toFixed(4) : '—' },
                ].map(({ label, value }) => (
                  <div key={label} className="flex justify-between items-center py-2 border-b border-slate-100 last:border-0">
                    <dt className="text-xs text-slate-500">{label}</dt>
                    <dd className="text-xs font-semibold text-slate-800 font-mono">{value}</dd>
                  </div>
                ))}
              </dl>

              {/* Request ID */}
              {request_id && (
                <p className="mt-4 text-[10px] text-slate-400 font-mono break-all">
                  Request ID: {request_id}
                </p>
              )}
            </div>
          </div>

          {/* Footer bar */}
          <div className="px-8 py-4 bg-slate-50 border-t border-slate-100 flex items-center justify-between gap-4">
            <p className="text-xs text-slate-400 italic">
              For research use only. This result does not constitute clinical advice.
            </p>
            <button onClick={onReset} className="btn-ghost gap-1.5 text-xs">
              <RotateCcw size={13} />
              New Prediction
            </button>
          </div>
        </div>
      </motion.section>
    </AnimatePresence>
  )
}
