import { useState } from "react"
import { Mail, Lock, Eye, EyeOff, AlertCircle, Loader2 } from "lucide-react"
import { signInWithEmail, signUpWithEmail, signInWithGoogle } from "@/firebase"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/utils"

type Mode = "signin" | "signup"

function GoogleIcon() {
  return (
    <svg className="w-4 h-4" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
      <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
      <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
      <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/>
      <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
    </svg>
  )
}

const FIREBASE_ERRORS: Record<string, string> = {
  "auth/invalid-credential": "Incorrect email or password.",
  "auth/user-not-found": "No account found with this email.",
  "auth/wrong-password": "Incorrect password.",
  "auth/email-already-in-use": "An account with this email already exists.",
  "auth/weak-password": "Password must be at least 6 characters.",
  "auth/invalid-email": "Please enter a valid email address.",
  "auth/too-many-requests": "Too many attempts. Please try again later.",
  "auth/popup-closed-by-user": "",
}

function friendlyError(code: string): string {
  return FIREBASE_ERRORS[code] ?? "Something went wrong. Please try again."
}

interface LoginPageProps {
  initialMode?: Mode
  onBack?: () => void
  onAuthenticated?: () => void
}

export function LoginPage({
  initialMode = "signin",
  onBack,
  onAuthenticated,
}: LoginPageProps) {
  const [mode, setMode] = useState<Mode>(initialMode)
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [showPassword, setShowPassword] = useState(false)
  const [loading, setLoading] = useState(false)
  const [googleLoading, setGoogleLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [focused, setFocused] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      if (mode === "signin") {
        await signInWithEmail(email, password)
      } else {
        await signUpWithEmail(email, password)
      }
      onAuthenticated?.()
    } catch (err: unknown) {
      const code = (err as { code?: string })?.code ?? ""
      const msg = friendlyError(code)
      if (msg) setError(msg)
    } finally {
      setLoading(false)
    }
  }

  const handleGoogle = async () => {
    setError(null)
    setGoogleLoading(true)
    try {
      await signInWithGoogle()
      onAuthenticated?.()
    } catch (err: unknown) {
      const code = (err as { code?: string })?.code ?? ""
      const msg = friendlyError(code)
      if (msg) setError(msg)
    } finally {
      setGoogleLoading(false)
    }
  }

  return (
    <div
      className="relative w-full max-w-lg"
      onFocusCapture={() => setFocused(true)}
      onBlurCapture={(e) => {
        if (!e.currentTarget.contains(e.relatedTarget as Node)) setFocused(false)
      }}
    >
      {/* Glow backdrop */}
      <div
        className={cn(
          "absolute -inset-8 rounded-[2rem] bg-purple-500/25 blur-3xl transition-opacity duration-500 pointer-events-none",
          focused ? "opacity-100" : "opacity-50"
        )}
      />

      {/* Card */}
      <div className="relative rounded-3xl border border-white/15 bg-zinc-950/55 px-8 py-9 shadow-2xl shadow-black/30 backdrop-blur-2xl sm:px-10">
          <div className="mb-6">
            <h1 className="text-2xl font-semibold text-white">
              {mode === "signin" ? "Welcome back" : "Create account"}
            </h1>
            <p className="text-sm text-white/60 mt-1.5">
              {mode === "signin"
                ? "Sign in to access your candidate database."
                : "Sign up to start building your talent pool."}
            </p>
          </div>

          {/* Google */}
          <button
            type="button"
            onClick={handleGoogle}
            disabled={googleLoading || loading}
            className="w-full flex items-center justify-center gap-2.5 border border-white/15 bg-white/10 rounded-xl px-4 py-3 text-sm font-medium text-white hover:bg-white/15 hover:border-white/25 transition-all duration-150 disabled:opacity-50 disabled:cursor-not-allowed mb-5"
          >
            {googleLoading ? (
              <Loader2 className="w-4 h-4 animate-spin text-white/60" />
            ) : (
              <GoogleIcon />
            )}
            Continue with Google
          </button>

          <div className="relative flex items-center gap-3 mb-5">
            <div className="flex-1 h-px bg-white/10" />
            <span className="text-xs text-white/40">or</span>
            <div className="flex-1 h-px bg-white/10" />
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Email */}
            <div>
              <label className="flex items-center gap-1.5 text-sm font-medium text-white/80 mb-1.5">
                <Mail className="w-3.5 h-3.5 text-white/45" /> Email
              </label>
              <Input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                autoComplete="email"
                required
                className="h-11 border-white/15 bg-black/25 text-white placeholder:text-white/35 focus:border-purple-400 focus:ring-purple-500/20"
              />
            </div>

            {/* Password */}
            <div>
              <label className="flex items-center gap-1.5 text-sm font-medium text-white/80 mb-1.5">
                <Lock className="w-3.5 h-3.5 text-white/45" /> Password
              </label>
              <div className="relative">
                <Input
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  autoComplete={mode === "signup" ? "new-password" : "current-password"}
                  required
                  className="h-11 border-white/15 bg-black/25 pr-10 text-white placeholder:text-white/35 focus:border-purple-400 focus:ring-purple-500/20"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((v) => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-white/40 hover:text-white/70 transition-colors"
                  tabIndex={-1}
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            {error && (
              <div className="flex items-start gap-2 rounded-lg bg-red-500/10 border border-red-400/20 px-3 py-2.5 text-sm text-red-200">
                <AlertCircle className="w-4 h-4 mt-0.5 flex-none" />
                {error}
              </div>
            )}

            <Button
              type="submit"
              disabled={loading || googleLoading}
              className="w-full rounded-xl bg-purple-600 hover:bg-purple-500"
              size="lg"
            >
              {loading ? (
                <><Loader2 className="w-4 h-4 animate-spin" /> {mode === "signin" ? "Signing in…" : "Creating account…"}</>
              ) : (
                mode === "signin" ? "Sign in" : "Create account"
              )}
            </Button>
          </form>

          {/* Toggle */}
          <p className="text-center text-sm text-white/55 mt-5">
            {mode === "signin" ? "Don't have an account?" : "Already have an account?"}{" "}
            <button
              type="button"
              onClick={() => { setMode(mode === "signin" ? "signup" : "signin"); setError(null) }}
              className="text-purple-300 font-medium hover:text-purple-200 transition-colors"
            >
              {mode === "signin" ? "Sign up" : "Sign in"}
            </button>
          </p>

          {onBack && (
            <p className="text-center mt-3">
              <button
                type="button"
                onClick={onBack}
                className="text-xs text-white/45 hover:text-white/70 transition-colors"
              >
                ← Back to home
              </button>
            </p>
          )}
      </div>
    </div>
  )
}
