import { motion } from 'framer-motion'
import { Upload, ClipboardList, Layers, Target } from 'lucide-react'

const steps = [
  {
    icon:    Upload,
    number:  '01',
    title:   'Upload Methylation File',
    desc:    'Provide a tab-separated TCGA sesame level3 betas text file with CpG probe IDs and beta values.',
    color:   'teal',
  },
  {
    icon:    ClipboardList,
    number:  '02',
    title:   'Enter Clinical Features',
    desc:    '13 patient and diagnosis features are encoded using fitted label encoders from the training dataset.',
    color:   'blue',
  },
  {
    icon:    Layers,
    number:  '03',
    title:   'Generate Embeddings',
    desc:    'A PyTorch encoder compresses methylation into 150 latent features. A contrastive model produces a 128-dim stage-aware embedding.',
    color:   'violet',
  },
  {
    icon:    Target,
    number:  '04',
    title:   'Predict Cancer Stage',
    desc:    'The DriftNet dual-branch classifier fuses methylation and clinical representations to output Stage I, II, or III.',
    color:   'slate',
  },
]

const colorMap = {
  teal:   { bg: 'bg-teal-50',   icon: 'text-teal-600',   border: 'border-teal-100',  num: 'text-teal-300' },
  blue:   { bg: 'bg-blue-50',   icon: 'text-blue-600',   border: 'border-blue-100',  num: 'text-blue-300' },
  violet: { bg: 'bg-violet-50', icon: 'text-violet-600', border: 'border-violet-100',num: 'text-violet-300' },
  slate:  { bg: 'bg-slate-50',  icon: 'text-slate-600',  border: 'border-slate-200', num: 'text-slate-300' },
}

export default function WorkflowSteps() {
  return (
    <section className="bg-slate-50 py-16 border-b border-slate-200/80">
      <div className="max-w-7xl mx-auto px-6">
        {/* Section header */}
        <div className="text-center mb-10">
          <p className="text-xs font-semibold text-teal-600 uppercase tracking-widest mb-2">
            How It Works
          </p>
          <h2 className="text-2xl font-bold text-slate-900">
            Four-Step Inference Pipeline
          </h2>
        </div>

        {/* Steps grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
          {steps.map((step, i) => {
            const Icon = step.icon
            const c = colorMap[step.color]
            return (
              <motion.div
                key={step.title}
                initial={{ opacity: 0, y: 16 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.4, delay: i * 0.1 }}
                className={`relative card p-6 border ${c.border} hover:shadow-card-md transition-shadow duration-200`}
              >
                {/* Connector arrow (all except last) */}
                {i < steps.length - 1 && (
                  <div className="hidden lg:block absolute -right-3 top-1/2 -translate-y-1/2 z-10">
                    <div className="w-6 h-px bg-slate-300" />
                    <div className="absolute right-0 top-1/2 -translate-y-1/2 w-0 h-0
                      border-t-[4px] border-t-transparent
                      border-b-[4px] border-b-transparent
                      border-l-[6px] border-l-slate-300" />
                  </div>
                )}

                {/* Step number */}
                <span className={`text-3xl font-black ${c.num} absolute top-4 right-5 leading-none select-none`}>
                  {step.number}
                </span>

                {/* Icon */}
                <div className={`w-9 h-9 rounded-lg ${c.bg} flex items-center justify-center mb-4`}>
                  <Icon size={18} className={c.icon} />
                </div>

                {/* Content */}
                <h3 className="text-sm font-semibold text-slate-900 mb-2">{step.title}</h3>
                <p className="text-xs text-slate-500 leading-relaxed">{step.desc}</p>
              </motion.div>
            )
          })}
        </div>
      </div>
    </section>
  )
}
