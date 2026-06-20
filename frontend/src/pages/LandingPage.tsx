import { MeshGradient, PulsingBorder } from "@paper-design/shaders-react"
import { motion } from "framer-motion"
import { Zap } from "lucide-react"

interface LandingPageProps {
  onGetStarted: () => void
}

export function LandingPage({ onGetStarted }: LandingPageProps) {
  return (
    <div className="relative h-screen overflow-hidden bg-black select-none">
      {/* Animated mesh gradient */}
      <MeshGradient
        colors={["#000000", "#7c3aed", "#ffffff", "#1e1b4b", "#4c1d95"]}
        speed={0.3}
        distortion={0.4}
        className="absolute inset-0"
        style={{ width: "100%", height: "100%" }}
      />

      {/* Gradient overlays for text legibility */}
      <div className="absolute inset-x-0 top-0 h-36 bg-gradient-to-b from-black/70 to-transparent pointer-events-none z-10" />
      <div className="absolute inset-x-0 bottom-0 h-72 bg-gradient-to-t from-black/80 to-transparent pointer-events-none z-10" />

      {/* ── Header ── */}
      <header className="absolute top-0 left-0 right-0 z-20 flex items-center justify-between px-8 py-5">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-xl bg-purple-600 flex items-center justify-center flex-none shadow-lg shadow-purple-900/50">
            <Zap className="w-4 h-4 text-white" />
          </div>
          <span className="text-white font-semibold text-sm tracking-tight">
            Candidate Intelligence
          </span>
        </div>

        <button
          onClick={onGetStarted}
          className="h-8 px-5 rounded-full bg-white text-black text-xs font-medium hover:bg-gray-100 transition-colors shadow-md"
        >
          Sign In
        </button>
      </header>

      {/* ── Hero content — bottom left ── */}
      <div className="absolute bottom-8 left-8 z-20 max-w-lg">
        {/* Badge */}
        <div className="inline-flex items-center gap-2 rounded-full bg-white/5 border border-white/10 backdrop-blur-sm px-3.5 py-1.5 mb-5">
          <span className="text-purple-400 text-xs">✦</span>
          <span className="text-[11px] font-light text-white/70 tracking-wide">AI-Powered Talent Discovery</span>
        </div>

        {/* Headline */}
        <h1 className="text-5xl md:text-6xl font-light text-white leading-[1.1] mb-4">
          <span style={{ fontFamily: "'Instrument Serif', serif", fontStyle: "italic", fontWeight: 500 }}>
            Intelligent
          </span>
          {" "}Candidate
          <br />
          Intelligence Engine
        </h1>

        {/* Description */}
        <p className="text-xs font-light text-white/55 mb-7 max-w-sm leading-relaxed">
          Unify GitHub profiles, LinkedIn data, and resumes into AI-powered candidate profiles.
          Search semantically. Compare comprehensively. Hire confidently.
        </p>

        {/* CTAs */}
        <div className="flex items-center gap-3">
          <button
            onClick={onGetStarted}
            className="px-7 py-2.5 rounded-full border border-white/25 text-white text-xs font-medium hover:bg-white/10 hover:border-white/40 transition-all duration-150"
          >
            Sign In
          </button>
          <button
            onClick={onGetStarted}
            className="px-7 py-2.5 rounded-full bg-white text-black text-xs font-medium hover:bg-gray-100 transition-all duration-150 shadow-lg"
          >
            Get Started →
          </button>
        </div>
      </div>

      {/* ── Pulsing circle — bottom right ── */}
      <div
        className="absolute bottom-8 right-8 z-30 flex items-center justify-center"
        style={{ width: 80, height: 80 }}
      >
        {/* Pulsing border ring */}
        <PulsingBorder
          colors={["#4285F4", "#7c3aed", "#EA4335", "#34A853", "#f472b6", "#FBBC05"]}
          speed={0.8}
          style={{
            position: "absolute",
            inset: 0,
            width: "100%",
            height: "100%",
            borderRadius: "50%",
          }}
        />

        {/* Rotating text */}
        <div
          style={{
            position: "absolute",
            inset: 0,
            transform: "scale(1.65)",
            transformOrigin: "center",
          }}
        >
          <motion.svg
            viewBox="0 0 100 100"
            animate={{ rotate: 360 }}
            transition={{ duration: 22, repeat: Infinity, ease: "linear" }}
            style={{ width: "100%", height: "100%" }}
          >
            <defs>
              <path
                id="cie-text-circle"
                d="M 50,50 m -36,0 a 36,36 0 1,1 72,0 a 36,36 0 1,1 -72,0"
              />
            </defs>
            <text
              fontSize="7.2"
              fill="rgba(255,255,255,0.65)"
              style={{ fontFamily: "'Instrument Serif', serif" }}
            >
              <textPath href="#cie-text-circle">
                Candidate Intelligence Engine • Candidate Intelligence Engine •
              </textPath>
            </text>
          </motion.svg>
        </div>
      </div>
    </div>
  )
}
