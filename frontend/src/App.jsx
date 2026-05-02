import { useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Loader2, FlaskConical, RotateCcw } from 'lucide-react'

import Header        from './components/Header'
import Hero          from './components/Hero'
import WorkflowSteps from './components/WorkflowSteps'
import FileUploadCard from './components/FileUploadCard'
import ClinicalFormCard from './components/ClinicalFormCard'
import ResultPanel   from './components/ResultPanel'
import ErrorBanner   from './components/ErrorBanner'
import Footer        from './components/Footer'

import { predictStage }         from './api/predict'
import { INITIAL_CLINICAL_VALUES } from './data/clinicalData'

export default function App() {
  const [file,           setFile]           = useState(null)
  const [clinicalValues, setClinicalValues] = useState(INITIAL_CLINICAL_VALUES)
  const [isLoading,      setIsLoading]      = useState(false)
  const [result,         setResult]         = useState(null)
  const [error,          setError]          = useState(null)

  // ── handlers ────────────────────────────────────────────────────────
  const handleClinicalChange = (field, value) =>
    setClinicalValues(prev => ({ ...prev, [field]: value }))

  const handleReset = () => {
    setFile(null)
    setClinicalValues(INITIAL_CLINICAL_VALUES)
    setResult(null)
    setError(null)
    // Scroll back to top
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const handleSubmit = async () => {
    setError(null)
    setResult(null)

    // Validate file
    if (!file) {
      setError({
        type: 'validation',
        message: 'Please upload a methylation .txt file before running the prediction.',
      })
      return
    }

    // Validate all clinical fields
    const missingFields = Object.entries(clinicalValues)
      .filter(([, v]) => v === '' || v === null || v === undefined)
      .map(([k]) => k)

    if (missingFields.length > 0) {
      setError({
        type: 'validation',
        message: `${missingFields.length} clinical field${missingFields.length > 1 ? 's are' : ' is'} missing. Please complete all fields in the form.`,
      })
      return
    }

    // Submit
    setIsLoading(true)
    try {
      const res = await predictStage(file, clinicalValues)

      if (res.success === false) {
        // Backend returned a structured error payload
        setError({
          type:    'api',
          message: res.error_message ?? 'The prediction did not complete successfully.',
          hint:    res.hint,
        })
      } else {
        setResult(res)
        // Scroll to result after short delay
        setTimeout(() => {
          document.getElementById('result')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
        }, 200)
      }
    } catch (err) {
      // Network or HTTP error
      if (err.status === 422) {
        setError({
          type:    'api',
          message: 'The server rejected one or more field values. Check that clinical field values match the allowed options.',
          hint:    err.message,
        })
      } else if (!navigator.onLine || err.message.toLowerCase().includes('fetch')) {
        setError({
          type:    'network',
          message: 'Cannot reach the DriftNet backend. Make sure the server is running at http://localhost:8000.',
        })
      } else {
        setError({
          type:    'api',
          message: err.message ?? 'An unexpected error occurred.',
        })
      }
    } finally {
      setIsLoading(false)
    }
  }

  const filledCount   = Object.values(clinicalValues).filter(v => v !== '').length
  const totalCount    = Object.keys(clinicalValues).length
  const isFormComplete = file && filledCount === totalCount

  // ── render ──────────────────────────────────────────────────────────
  return (
    <div className="min-h-screen bg-slate-50 flex flex-col">
      <Header />

      <main className="flex-1">
        {/* Hero */}
        <Hero />

        {/* Workflow steps */}
        <WorkflowSteps />

        {/* ── Prediction section ── */}
        <section className="max-w-7xl mx-auto px-6 py-12">
          {/* Section label */}
          <div className="mb-8">
            <p className="text-xs font-semibold text-teal-600 uppercase tracking-widest mb-1">
              Run a Prediction
            </p>
            <h2 className="text-2xl font-bold text-slate-900">
              Upload & Classify
            </h2>
            <p className="text-sm text-slate-500 mt-1.5">
              Provide a methylation file and complete the clinical form, then click Predict.
            </p>
          </div>

          {/* Two-column layout */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">
            <FileUploadCard  file={file}          onFileChange={setFile} />
            <ClinicalFormCard values={clinicalValues} onChange={handleClinicalChange} />
          </div>

          {/* Error banner */}
          <AnimatePresence>
            {error && (
              <motion.div
                key="error"
                initial={{ opacity: 0, y: -6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                className="mt-5"
              >
                <ErrorBanner error={error} onDismiss={() => setError(null)} />
              </motion.div>
            )}
          </AnimatePresence>

          {/* Submit / action bar */}
          <div className="mt-8 flex flex-col sm:flex-row items-center justify-center gap-4">
            <button
              onClick={handleSubmit}
              disabled={isLoading}
              className="btn-primary text-base px-10 py-4 min-w-[260px] shadow-md hover:shadow-lg"
            >
              {isLoading ? (
                <>
                  <Loader2 size={18} className="animate-spin" />
                  Running DriftNet…
                </>
              ) : (
                <>
                  <FlaskConical size={18} />
                  Predict Cancer Stage
                </>
              )}
            </button>

            {/* Clear / reset  */}
            {(file || filledCount > 0 || result) && !isLoading && (
              <motion.button
                initial={{ opacity: 0, x: 8 }}
                animate={{ opacity: 1, x: 0 }}
                onClick={handleReset}
                className="btn-ghost"
              >
                <RotateCcw size={14} />
                Clear form
              </motion.button>
            )}
          </div>

          {/* Form completion hint */}
          {!isLoading && !isFormComplete && (
            <p className="text-center text-xs text-slate-400 mt-3">
              {!file
                ? 'Upload a methylation file to continue.'
                : `${totalCount - filledCount} clinical field${totalCount - filledCount > 1 ? 's' : ''} remaining.`
              }
            </p>
          )}

          {/* Loading overlay message */}
          <AnimatePresence>
            {isLoading && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="mt-5 text-center space-y-1"
              >
                <p className="text-sm font-medium text-slate-600">
                  Processing methylation data and running inference…
                </p>
                <p className="text-xs text-slate-400">
                  This may take 10–30 seconds depending on your hardware.
                </p>
              </motion.div>
            )}
          </AnimatePresence>
        </section>

        {/* ── Result panel ── */}
        <AnimatePresence>
          {result && !isLoading && (
            <ResultPanel result={result} onReset={handleReset} />
          )}
        </AnimatePresence>
      </main>

      <Footer />
    </div>
  )
}
