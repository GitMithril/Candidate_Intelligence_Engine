import { useState, useRef } from "react"
import { Upload, FileText, GitFork, Link2, CheckCircle, AlertCircle, Loader2, X, ExternalLink } from "lucide-react"
import { ingestSingle, type IngestResponse } from "@/api"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { ProfileModal } from "@/components/ProfileModal"
import { cn } from "@/lib/utils"

export function SingleUpload() {
  const [linkedinUrl, setLink2Url] = useState("")
  const [githubUsername, setGitForkUsername] = useState("")
  const [file, setFile] = useState<File | null>(null)
  const [dragging, setDragging] = useState(false)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<IngestResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [modalOpen, setModalOpen] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleFile = (f: File) => {
    if (!f.name.toLowerCase().endsWith(".pdf")) {
      setError("Only PDF files are accepted.")
      return
    }
    setFile(f)
    setError(null)
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setDragging(false)
    const f = e.dataTransfer.files[0]
    if (f) handleFile(f)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!linkedinUrl && !githubUsername && !file) {
      setError("Provide at least one of: LinkedIn URL, GitHub username, or resume PDF.")
      return
    }
    if (linkedinUrl && !/^https:\/\/(www\.)?linkedin\.com\/in\/[^/\s]+\/?$/.test(linkedinUrl)) {
      setError("LinkedIn URL must be in the format: https://www.linkedin.com/in/profile-name/")
      return
    }
    setLoading(true)
    setResult(null)
    setError(null)
    const form = new FormData()
    if (linkedinUrl) form.append("linkedin_url", linkedinUrl)
    if (githubUsername) form.append("github_username", githubUsername)
    if (file) form.append("resume", file)
    try {
      const data = await ingestSingle(form)
      setResult(data)
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(msg ?? "Something went wrong. Please try again.")
    } finally {
      setLoading(false)
    }
  }

  const reset = () => {
    setResult(null)
    setError(null)
    setFile(null)
    setModalOpen(false)
    setLink2Url("")
    setGitForkUsername("")
  }

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="max-w-xl mx-auto px-6 py-10">
        <div className="mb-8">
          <h1 className="text-2xl font-semibold text-gray-900 tracking-tight">Add a candidate</h1>
          <p className="text-sm text-gray-500 mt-1">
            Provide any combination — the system merges all sources into one profile.
          </p>
        </div>

        {result ? (
          <ProfileResult result={result} onReset={reset} onViewFull={() => setModalOpen(true)} />
        ) : (
          <form onSubmit={handleSubmit} className="space-y-5">
            {/* LinkedIn */}
            <Field label="LinkedIn URL" icon={<Link2 className="w-4 h-4 text-gray-400" />}>
              <Input
                value={linkedinUrl}
                onChange={(e) => setLink2Url(e.target.value)}
                placeholder="https://linkedin.com/in/username"
                type="url"
              />
            </Field>

            {/* GitHub */}
            <Field label="GitHub Username" icon={<GitFork className="w-4 h-4 text-gray-400" />}>
              <Input
                value={githubUsername}
                onChange={(e) => setGitForkUsername(e.target.value)}
                placeholder="username"
              />
            </Field>

            {/* PDF Drop */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">
                <span className="flex items-center gap-1.5">
                  <FileText className="w-4 h-4 text-gray-400" /> Resume PDF
                </span>
              </label>
              <div
                onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
                onDragLeave={() => setDragging(false)}
                onDrop={handleDrop}
                onClick={() => fileInputRef.current?.click()}
                className={cn(
                  "relative flex flex-col items-center justify-center rounded-xl border-2 border-dashed cursor-pointer transition-all duration-150 py-8 px-4",
                  dragging ? "border-purple-400 bg-purple-50" : "border-gray-200 bg-gray-50 hover:border-purple-300 hover:bg-purple-50/40"
                )}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".pdf"
                  className="hidden"
                  onChange={(e) => { const f = e.target.files?.[0]; if (f) handleFile(f) }}
                />
                {file ? (
                  <div className="flex items-center gap-2">
                    <FileText className="w-5 h-5 text-purple-600" />
                    <span className="text-sm font-medium text-gray-800">{file.name}</span>
                    <button
                      type="button"
                      onClick={(e) => { e.stopPropagation(); setFile(null) }}
                      className="ml-1 text-gray-400 hover:text-gray-600"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                ) : (
                  <>
                    <Upload className="w-6 h-6 text-gray-400 mb-2" />
                    <p className="text-sm text-gray-500">
                      Drop PDF here or <span className="text-purple-600 font-medium">browse</span>
                    </p>
                  </>
                )}
              </div>
            </div>

            {error && (
              <div className="flex items-start gap-2 rounded-lg bg-red-50 border border-red-100 px-3 py-2.5 text-sm text-red-600">
                <AlertCircle className="w-4 h-4 mt-0.5 flex-none" />
                {error}
              </div>
            )}

            <Button type="submit" disabled={loading} className="w-full" size="lg">
              {loading ? (
                <><Loader2 className="w-4 h-4 animate-spin" /> Processing…</>
              ) : (
                <><Upload className="w-4 h-4" /> Build Profile</>
              )}
            </Button>
          </form>
        )}
      </div>

      <ProfileModal
        profile={result}
        open={modalOpen}
        onClose={() => setModalOpen(false)}
      />
    </div>
  )
}

function Field({ label, icon, children }: { label: string; icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <div>
      <label className="flex items-center gap-1.5 text-sm font-medium text-gray-700 mb-1.5">
        {icon} {label}
      </label>
      {children}
    </div>
  )
}

function ProfileResult({ result, onReset, onViewFull }: { result: IngestResponse; onReset: () => void; onViewFull: () => void }) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white shadow-sm overflow-hidden">
      {/* Header */}
      <div className="bg-purple-50 border-b border-purple-100 px-5 py-4 flex items-center gap-3">
        <CheckCircle className="w-5 h-5 text-purple-600 flex-none" />
        <div className="flex-1">
          <div className="text-sm font-semibold text-purple-900">Profile created</div>
          <div className="text-xs text-purple-600">Stored in MongoDB · Embedded in Pinecone</div>
        </div>
        <Button variant="ghost" size="sm" onClick={onViewFull} className="text-purple-600 hover:bg-purple-100 gap-1.5">
          <ExternalLink className="w-3.5 h-3.5" /> Full profile
        </Button>
        <Button variant="ghost" size="sm" onClick={onReset} className="text-purple-600 hover:bg-purple-100">
          Add another
        </Button>
      </div>

      {/* Body */}
      <div className="p-5 space-y-4">
        <div>
          <h2 className="text-xl font-semibold text-gray-900">{result.name ?? "Unknown"}</h2>
          {result.headline && <p className="text-sm text-gray-500 mt-0.5">{result.headline}</p>}
          {(result.current_role || result.current_company) && (
            <p className="text-sm text-gray-600 mt-1">
              {[result.current_role, result.current_company].filter(Boolean).join(" · ")}
            </p>
          )}
          {result.location && <p className="text-xs text-gray-400 mt-0.5">{result.location}</p>}
        </div>

        {result.skills?.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {result.skills.slice(0, 12).map((s) => (
              <Badge key={s} variant="purple">{s}</Badge>
            ))}
            {result.skills.length > 12 && (
              <Badge variant="gray">+{result.skills.length - 12} more</Badge>
            )}
          </div>
        )}

        {result.missing_links.length > 0 && (
          <div className="flex items-start gap-2 rounded-lg bg-amber-50 border border-amber-100 px-3 py-2.5 text-xs text-amber-700">
            <AlertCircle className="w-3.5 h-3.5 mt-0.5 flex-none" />
            <span>
              Not found in resume: <strong>{result.missing_links.join(", ")}</strong>. You can add them by resubmitting.
            </span>
          </div>
        )}

        <div className="flex flex-wrap gap-3">
          {result.source_urls?.github && (
            <a href={result.source_urls.github} target="_blank" rel="noopener noreferrer"
              className="flex items-center gap-1.5 text-xs text-gray-600 hover:text-purple-700 border border-gray-200 rounded-md px-2.5 py-1.5 transition-colors">
              <GitFork className="w-3 h-3" /> GitHub
            </a>
          )}
          {result.source_urls?.linkedin && (
            <a href={result.source_urls.linkedin} target="_blank" rel="noopener noreferrer"
              className="flex items-center gap-1.5 text-xs text-gray-600 hover:text-purple-700 border border-gray-200 rounded-md px-2.5 py-1.5 transition-colors">
              <Link2 className="w-3 h-3" /> LinkedIn
            </a>
          )}
        </div>
      </div>
    </div>
  )
}
