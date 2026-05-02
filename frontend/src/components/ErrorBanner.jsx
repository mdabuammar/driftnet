import { AlertCircle, X } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'

const ERROR_TITLES = {
  validation: 'Incomplete Form',
  api:        'Prediction Error',
  network:    'Connection Error',
}

export default function ErrorBanner({ error, onDismiss }) {
  if (!error) return null

  const title = ERROR_TITLES[error.type] ?? 'Error'

  return (
    <AnimatePresence>
      <motion.div
        key={error.message}
        initial={{ opacity: 0, y: -8 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -8 }}
        transition={{ duration: 0.25 }}
        className="flex items-start gap-3 bg-red-50 border border-red-200 rounded-xl px-4 py-4"
      >
        <AlertCircle size={16} className="text-red-500 mt-0.5 shrink-0" />
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-red-800">{title}</p>
          <p className="text-sm text-red-700 mt-0.5 break-words">{error.message}</p>
          {error.hint && (
            <p className="text-xs text-red-500 mt-1.5 italic">{error.hint}</p>
          )}
        </div>
        {onDismiss && (
          <button
            onClick={onDismiss}
            className="text-red-400 hover:text-red-600 transition-colors"
          >
            <X size={14} />
          </button>
        )}
      </motion.div>
    </AnimatePresence>
  )
}
