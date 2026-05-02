import { motion } from 'framer-motion'
import { Dna, ChevronDown } from 'lucide-react'

export default function Hero() {
  return (
    <section className="relative overflow-hidden bg-white border-b border-slate-200/80">
      {/* Subtle dot grid background */}
      <div
        className="absolute inset-0 opacity-40"
        style={{
          backgroundImage: 'radial-gradient(circle, #CBD5E1 1px, transparent 1px)',
          backgroundSize: '28px 28px',
        }}
      />
      {/* Gradient overlay */}
      <div className="absolute inset-0 bg-gradient-to-b from-white via-white/70 to-white" />

      <div className="relative max-w-7xl mx-auto px-6 py-20 lg:py-28">
        <div className="max-w-3xl mx-auto text-center">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
          >
            {/* Title */}
            <h1 className="text-5xl lg:text-6xl font-bold text-slate-900 leading-[1.1] tracking-tight mb-5">
              Drift
              <span className="text-teal-600">Net</span>
            </h1>

            {/* Subtitle */}
            <p className="text-xl font-medium text-slate-600 mb-4 text-balance">
              A Contrastive Learning for Pan Cancer Stage Classification
            </p>

            {/* Description */}
            <p className="text-base text-slate-500 max-w-xl mx-auto leading-relaxed text-balance">
              Upload one methylation profile and enter clinical features to receive
              a Stage I, II, or III prediction — powered by contrastive learning
              and a dual-branch neural classifier.
            </p>

            {/* Metadata pills */}
            <div className="flex flex-wrap items-center justify-center gap-3 mt-8">
              {[
                '550K CpG Probes',
                '150 Latent Features',
                '128-dim Contrastive Embedding',
                '13 Clinical Features',
              ].map(tag => (
                <span
                  key={tag}
                  className="text-xs font-medium text-slate-500 bg-slate-100 px-3 py-1 rounded-full border border-slate-200"
                >
                  {tag}
                </span>
              ))}
            </div>
          </motion.div>
        </div>

        {/* Scroll cue */}
        <motion.div
          className="flex justify-center mt-14"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.8, duration: 0.5 }}
        >
          <ChevronDown size={20} className="text-slate-300 animate-bounce" />
        </motion.div>
      </div>
    </section>
  )
}
