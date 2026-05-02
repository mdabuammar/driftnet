import { ClipboardList, HelpCircle } from 'lucide-react'
import {
  CLINICAL_OPTIONS,
  CLINICAL_LABELS,
  CLINICAL_HINTS,
  CLINICAL_GROUPS,
} from '../data/clinicalData'

function FieldSelect({ fieldKey, value, onChange }) {
  const options = CLINICAL_OPTIONS[fieldKey] || []
  return (
    <select
      id={fieldKey}
      value={value}
      onChange={(e) => onChange(fieldKey, e.target.value)}
      className="select-base"
    >
      <option value="">Select…</option>
      {options.map((opt) => (
        <option key={opt} value={opt}>{opt}</option>
      ))}
    </select>
  )
}

function FieldNumber({ fieldKey, value, onChange }) {
  return (
    <input
      id={fieldKey}
      type="number"
      min="0"
      step="1"
      value={value}
      onChange={(e) => onChange(fieldKey, e.target.value)}
      placeholder="e.g. 25069"
      className="input-base"
    />
  )
}

function FormField({ fieldKey, value, onChange }) {
  const label = CLINICAL_LABELS[fieldKey]
  const hint  = CLINICAL_HINTS[fieldKey]
  const isNumeric = fieldKey === 'diagnoses.age_at_diagnosis'
  const hasValue  = value !== '' && value !== null && value !== undefined

  return (
    <div>
      <label htmlFor={fieldKey} className="label-base flex items-center gap-1.5">
        {label}
        {!hasValue && (
          <span className="text-red-400 font-bold text-base leading-none">·</span>
        )}
        {hint && (
          <span className="group relative inline-flex">
            <HelpCircle size={11} className="text-slate-400 cursor-help" />
            <span className="
              absolute bottom-full left-1/2 -translate-x-1/2 mb-2
              w-44 text-center text-[10px] bg-slate-800 text-white px-2 py-1.5 rounded-lg
              opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity z-20
              whitespace-normal leading-snug
            ">
              {hint}
            </span>
          </span>
        )}
      </label>

      {isNumeric
        ? <FieldNumber fieldKey={fieldKey} value={value} onChange={onChange} />
        : <FieldSelect fieldKey={fieldKey} value={value} onChange={onChange} />
      }
    </div>
  )
}

export default function ClinicalFormCard({ values, onChange }) {
  const totalFields  = Object.keys(CLINICAL_LABELS).length
  const filledFields = Object.values(values).filter(v => v !== '').length

  return (
    <div className="card p-6 flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between mb-5">
        <div>
          <h2 className="text-base font-semibold text-slate-900">Clinical Features</h2>
          <p className="text-xs text-slate-500 mt-0.5">All 13 fields are required</p>
        </div>
        <div className="flex items-center gap-2">
          {/* Progress pill */}
          <span className={`text-xs font-semibold px-2.5 py-1 rounded-full
            ${filledFields === totalFields
              ? 'bg-emerald-100 text-emerald-700'
              : 'bg-slate-100 text-slate-600'
            }`}>
            {filledFields}/{totalFields}
          </span>
          <div className="w-8 h-8 rounded-lg bg-teal-50 flex items-center justify-center">
            <ClipboardList size={15} className="text-teal-600" />
          </div>
        </div>
      </div>

      {/* Progress bar */}
      <div className="mb-5 h-1 bg-slate-100 rounded-full overflow-hidden">
        <div
          className="h-full bg-teal-500 rounded-full transition-all duration-500"
          style={{ width: `${(filledFields / totalFields) * 100}%` }}
        />
      </div>

      {/* Field groups */}
      <div className="flex-1 space-y-6 overflow-y-auto max-h-[520px] pr-1">
        {CLINICAL_GROUPS.map((group) => (
          <div key={group.title}>
            {/* Group heading */}
            <div className="flex items-center gap-2 mb-3">
              <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                {group.title}
              </span>
              <div className="flex-1 h-px bg-slate-100" />
            </div>

            {/* Fields grid */}
            <div className={`grid gap-3 ${group.fields.length === 1 ? 'grid-cols-1' : 'grid-cols-1 sm:grid-cols-2'}`}>
              {group.fields.map((fieldKey) => (
                <FormField
                  key={fieldKey}
                  fieldKey={fieldKey}
                  value={values[fieldKey]}
                  onChange={onChange}
                />
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
