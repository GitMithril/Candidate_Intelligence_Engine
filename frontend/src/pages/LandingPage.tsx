import { MeshGradient } from "@paper-design/shaders-react"
import { AnimatePresence, motion } from "framer-motion"
import { LoginPage } from "@/pages/LoginPage"

interface LandingPageProps {
  isAuthenticated: boolean
  showLogin: boolean
  authMode: "signin" | "signup"
  onSignIn: () => void
  onGetStarted: () => void
  onBack: () => void
  onAuthenticated: () => void
}

export function LandingPage({
  isAuthenticated,
  showLogin,
  authMode,
  onSignIn,
  onGetStarted,
  onBack,
  onAuthenticated,
}: LandingPageProps) {
  const signInLabel = isAuthenticated ? "To Dashboard" : "Sign In"

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

      <AnimatePresence>
        {!showLogin && (
          <motion.header
            key="landing-header"
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -12 }}
            transition={{ duration: 0.22, ease: "easeOut" }}
            className="absolute top-0 left-0 right-0 z-20 flex items-center justify-between px-8 py-5"
          >
            <span className="text-white font-semibold text-sm tracking-tight">
              Candidate Lens
            </span>

            <motion.button
              onClick={onSignIn}
              whileHover={{ y: -1, scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              transition={{ duration: 0.15, ease: "easeOut" }}
              className="h-8 px-5 rounded-full bg-white text-black text-xs font-medium hover:bg-gray-100 transition-colors shadow-md"
            >
              {signInLabel}
            </motion.button>
          </motion.header>
        )}
      </AnimatePresence>

      <AnimatePresence mode="wait">
        {showLogin ? (
          <motion.div
            key="login"
            initial={{ opacity: 0, y: 14, scale: 0.985 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 8, scale: 0.99 }}
            transition={{ duration: 0.24, ease: "easeOut" }}
            className="absolute inset-0 z-20 flex items-center justify-center bg-black/20 px-4 backdrop-blur-[2px]"
          >
            <LoginPage
              initialMode={authMode}
              onBack={onBack}
              onAuthenticated={onAuthenticated}
            />
          </motion.div>
        ) : (
          <motion.div
            key="landing-hero"
            initial={{ opacity: 0, x: -12 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -18 }}
            transition={{ duration: 0.24, ease: "easeOut" }}
            className="absolute bottom-8 left-8 z-20 max-w-lg"
          >
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
              Scanning Engine
            </h1>

            {/* Description */}
            <p className="text-xs font-light text-white/55 mb-7 max-w-sm leading-relaxed">
              Unify GitHub profiles, LinkedIn data, and resumes into AI-powered candidate profiles.
              Search semantically. Compare comprehensively. Hire confidently.
            </p>

            {/* CTAs */}
            <div className="flex items-center gap-3">
              <motion.button
                onClick={onSignIn}
                whileHover={{ y: -1, scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                transition={{ duration: 0.15, ease: "easeOut" }}
                className="px-7 py-2.5 rounded-full border border-white/25 text-white text-xs font-medium hover:bg-white/10 hover:border-white/40 transition-all duration-150"
              >
                {signInLabel}
              </motion.button>
              <motion.button
                onClick={onGetStarted}
                whileHover={{ y: -1, scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                transition={{ duration: 0.15, ease: "easeOut" }}
                className="px-7 py-2.5 rounded-full bg-white text-black text-xs font-medium hover:bg-gray-100 transition-all duration-150 shadow-lg"
              >
                {isAuthenticated ? "To Dashboard →" : "Get Started →"}
              </motion.button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
