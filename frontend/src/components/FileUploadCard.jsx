import { useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Upload, FileText, X, CheckCircle2, AlertCircle } from 'lucide-react'

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

export default function FileUploadCard({ file, onFileChange }) {
  const inputRef = useRef(null)
  const [isDragging, setIsDragging] = useState(false)
  const [error, setError] = useState(null)

  const handleFile = (f) => {
    if (!f) return
    if (!f.name.endsWith('.txt')) {
      setError('Only .txt methylation files are accepted.')
      return
    }
    setError(null)
    onFileChange(f)
  }

  const handleDrop = (e) => {
    e.preventDefault()
    setIsDragging(false)
    const f = e.dataTransfer.files[0]
    handleFile(f)
  }

  const handleDragOver = (e) => { e.preventDefault(); setIsDragging(true) }
  const handleDragLeave = ()  => setIsDragging(false)

  const handleClear = (e) => {
    e.stopPropagation()
    onFileChange(null)
    setError(null)
    if (inputRef.current) inputRef.current.value = ''
  }

  return (
    <div className="card p-6 flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between mb-5">
        <div>
          <h2 className="text-base font-semibold text-slate-900">Methylation File</h2>
          <p className="text-xs text-slate-500 mt-0.5">Tab-separated .txt — no header required</p>
        </div>
        <div className="w-8 h-8 rounded-lg bg-teal-50 flex items-center justify-center">
          <Upload size={15} className="text-teal-600" />
        </div>
      </div>

      {/* Drop zone */}
      <div
        onClick={() => !file && inputRef.current?.click()}
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        className={`
          relative flex-1 min-h-[240px] flex flex-col items-center justify-center
          rounded-xl border-2 border-dashed cursor-pointer
          transition-all duration-200
          ${file
            ? 'border-emerald-300 bg-emerald-50/50 cursor-default'
            : isDragging
              ? 'border-teal-400 bg-teal-50 scale-[1.01]'
              : error
                ? 'border-red-300 bg-red-50/50 hover:border-red-400'
                : 'border-slate-300 bg-slate-50/50 hover:border-teal-400 hover:bg-teal-50/30'
          }
        `}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".txt"
          className="hidden"
          onChange={(e) => handleFile(e.target.files[0])}
        />

        <AnimatePresence mode="wait">
          {file ? (
            /* File selected state */
            <motion.div
              key="file"
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="flex flex-col items-center gap-3 px-6 text-center"
            >
              <div className="w-12 h-12 rounded-xl bg-emerald-100 flex items-center justify-center">
                <CheckCircle2 size={24} className="text-emerald-600" />
              </div>
              <div>
                <p className="text-sm font-semibold text-slate-800 break-all leading-snug">
                  {file.name}
                </p>
                <p className="text-xs text-slate-500 mt-1">{formatBytes(file.size)}</p>
              </div>
              <button
                onClick={handleClear}
                className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-red-500 transition-colors mt-1"
              >
                <X size={12} />
                Remove file
              </button>
            </motion.div>
          ) : (
            /* Empty state */
            <motion.div
              key="empty"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="flex flex-col items-center gap-3 px-6 text-center"
            >
              <div className={`w-12 h-12 rounded-xl flex items-center justify-center transition-colors
                ${isDragging ? 'bg-teal-200' : 'bg-slate-100'}`}>
                {isDragging
                  ? <Upload size={22} className="text-teal-600" />
                  : <FileText size={22} className="text-slate-400" />
                }
              </div>
              <div>
                <p className="text-sm font-medium text-slate-700">
                  {isDragging ? 'Drop your file here' : 'Drag & drop your file here'}
                </p>
                <p className="text-xs text-slate-400 mt-1">
                  or{' '}
                  <span className="text-teal-600 font-medium hover:text-teal-700 cursor-pointer">
                    click to browse
                  </span>
                </p>
              </div>
              <div className="mt-2 space-y-1">
                <p className="text-xs text-slate-400">Accepted format: <code className="bg-slate-100 px-1.5 py-0.5 rounded text-slate-600">.txt</code></p>
                <p className="text-xs text-slate-400">TCGA sesame level3 betas · EPIC array</p>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Error */}
      <AnimatePresence>
        {error && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="mt-3 flex items-start gap-2 text-xs text-red-600"
          >
            <AlertCircle size={13} className="mt-0.5 shrink-0" />
            {error}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Format reference */}
      <div className="mt-4 rounded-lg bg-slate-50 border border-slate-200 p-3">
        <p className="text-xs font-medium text-slate-500 mb-2">Expected file format</p>
        <code className="text-xs text-slate-600 leading-relaxed font-mono block">
          cg00000029{'  '}0.125476<br />
          cg00000108{'  '}0.967176<br />
          cg00000807{'  '}NA
        </code>
      </div>
    </div>
  )
}
