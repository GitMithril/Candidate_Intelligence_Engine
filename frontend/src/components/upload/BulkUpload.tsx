import { useState, useRef, useCallback, useEffect } from "react"
import { Upload, FolderOpen, FileText, X, Loader2, CheckCircle, AlertCircle, RefreshCw, ChevronDown, ChevronUp } from "lucide-react"
import { ingestBulk, pollBulkJob, type BulkJobStatus } from "@/api"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Progress } from "@/components/ui/progress"
import { cn } from "@/lib/utils"

export function BulkUpload() {
  const [files, setFiles] = useState<File[]>([])
  const [driveUrl, setDriveUrl] = useState("")
  const [dragging, setDragging] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [job, setJob] = useState<BulkJobStatus | null>(null)
  const [showErrors, setShowErrors] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const addFiles = useCallback((incoming: File[]) => {
    const valid = incoming.filter(
      (f) => f.name.toLowerCase().endsWith(".pdf") || f.name.toLowerCase().endsWith(".zip")
    )
    const invalid = incoming.filter(
      (f) => !f.name.toLowerCase().endsWith(".pdf") && !f.name.toLowerCase().endsWith(".zip")
    )
    if (invalid.length) setError(`Skipped ${invalid.length} non-PDF/ZIP file(s).`)
    setFiles((prev) => {
      const names = new Set(prev.map((f) => f.name))
      return [...prev, ...valid.filter((f) => !names.has(f.name))]
    })
  }, [])

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setDragging(false)
    addFiles(Array.from(e.dataTransfer.files))
  }

  const stopPolling = () => {
    if (pollRef.current) clearInterval(pollRef.current)
    pollRef.current = null
  }

  useEffect(() => () => stopPolling(), [])

  const startPolling = (jobId: string) => {
    pollRef.current = setInterval(async () => {
      try {
        const status = await pollBulkJob(jobId)
        setJob(status)
        if (status.status === "complete") stopPolling()
      } catch {
        stopPolling()
      }
    }, 2000)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!files.length && !driveUrl) {
      setError("Add PDF/ZIP files or paste a Google Drive folder URL.")
      return
    }
    setLoading(true)
    setError(null)
    setJob(null)
    const form = new FormData()
    files.forEach((f) => form.append("files", f))
    if (driveUrl) form.append("drive_url", driveUrl)
    try {
      const resp = await ingestBulk(form)
      const initial: BulkJobStatus = {
        job_id: resp.job_id,
        status: "pending",
        total: resp.total,
        processed: 0,
        failed: 0,
        errors: [],
      }
      setJob(initial)
      startPolling(resp.job_id)
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(msg ?? "Failed to start the job. Please try again.")
    } finally {
      setLoading(false)
    }
  }

  const reset = () => {
    stopPolling()
    setJob(null)
    setFiles([])
    setDriveUrl("")
    setError(null)
    setShowErrors(false)
  }

  const progressPct = job && job.total > 0
    ? Math.round(((job.processed + job.failed) / job.total) * 100)
    : 0

  const isDone = job?.status === "complete"

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="max-w-2xl mx-auto px-6 py-10">
        <div className="mb-8">
          <h1 className="text-2xl font-semibold text-gray-900 tracking-tight">Bulk import</h1>
          <p className="text-sm text-gray-500 mt-1">
            Upload up to 100 PDFs, a ZIP archive, or link a public Google Drive folder.
          </p>
        </div>

        {job ? (
          <JobProgress
            job={job}
            progressPct={progressPct}
            isDone={isDone}
            showErrors={showErrors}
            onToggleErrors={() => setShowErrors((v) => !v)}
            onReset={reset}
          />
        ) : (
          <form onSubmit={handleSubmit} className="space-y-5">
            {/* Drop zone */}
            <div
              onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
              onDragLeave={() => setDragging(false)}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
              className={cn(
                "relative flex flex-col items-center justify-center rounded-xl border-2 border-dashed cursor-pointer transition-all duration-150 py-12 px-4",
                dragging ? "border-purple-400 bg-purple-50" : "border-gray-200 bg-gray-50 hover:border-purple-300 hover:bg-purple-50/40"
              )}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,.zip"
                multiple
                className="hidden"
                onChange={(e) => { if (e.target.files) addFiles(Array.from(e.target.files)) }}
              />
              <Upload className="w-8 h-8 text-gray-300 mb-3" />
              <p className="text-sm font-medium text-gray-600">
                Drop PDFs or ZIPs here
              </p>
              <p className="text-xs text-gray-400 mt-1">
                or <span className="text-purple-600 font-medium">browse files</span> · up to 100 PDFs
              </p>
            </div>

            {/* File list */}
            {files.length > 0 && (
              <div className="rounded-xl border border-gray-100 bg-white overflow-hidden">
                <div className="flex items-center justify-between px-4 py-2.5 border-b border-gray-100 bg-gray-50">
                  <span className="text-xs font-medium text-gray-600">{files.length} file{files.length !== 1 ? "s" : ""} queued</span>
                  <button type="button" onClick={() => setFiles([])} className="text-xs text-gray-400 hover:text-red-500 transition-colors">
                    Clear all
                  </button>
                </div>
                <div className="max-h-36 overflow-y-auto divide-y divide-gray-50">
                  {files.map((f, i) => (
                    <div key={i} className="flex items-center gap-2.5 px-4 py-2">
                      <FileText className="w-3.5 h-3.5 text-purple-400 flex-none" />
                      <span className="text-xs text-gray-700 flex-1 truncate">{f.name}</span>
                      <span className="text-xs text-gray-400 flex-none">{(f.size / 1024).toFixed(0)} KB</span>
                      <button
                        type="button"
                        onClick={() => setFiles((p) => p.filter((_, j) => j !== i))}
                        className="text-gray-300 hover:text-red-400 transition-colors"
                      >
                        <X className="w-3 h-3" />
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Drive URL */}
            <div>
              <label className="flex items-center gap-1.5 text-sm font-medium text-gray-700 mb-1.5">
                <FolderOpen className="w-4 h-4 text-gray-400" />
                Google Drive Folder URL
                <span className="text-gray-400 font-normal">(public, optional)</span>
              </label>
              <Input
                value={driveUrl}
                onChange={(e) => setDriveUrl(e.target.value)}
                placeholder="https://drive.google.com/drive/folders/FOLDER_ID"
              />
            </div>

            {error && (
              <div className="flex items-start gap-2 rounded-lg bg-red-50 border border-red-100 px-3 py-2.5 text-sm text-red-600">
                <AlertCircle className="w-4 h-4 mt-0.5 flex-none" /> {error}
              </div>
            )}

            <Button type="submit" disabled={loading} className="w-full" size="lg">
              {loading ? (
                <><Loader2 className="w-4 h-4 animate-spin" /> Starting job…</>
              ) : (
                <><Upload className="w-4 h-4" /> Start Ingestion</>
              )}
            </Button>
          </form>
        )}
      </div>
    </div>
  )
}

function JobProgress({
  job, progressPct, isDone, showErrors, onToggleErrors, onReset
}: {
  job: BulkJobStatus
  progressPct: number
  isDone: boolean
  showErrors: boolean
  onToggleErrors: () => void
  onReset: () => void
}) {
  const statusColor = isDone
    ? job.failed === job.total ? "text-red-600" : "text-purple-700"
    : "text-gray-600"

  return (
    <div className="rounded-xl border border-gray-100 bg-white shadow-sm overflow-hidden">
      {/* Header */}
      <div className={cn("px-5 py-4 border-b border-gray-100 flex items-center gap-3",
        isDone ? "bg-purple-50" : "bg-gray-50")}>
        {isDone ? (
          <CheckCircle className="w-5 h-5 text-purple-600 flex-none" />
        ) : (
          <Loader2 className="w-5 h-5 text-purple-500 flex-none animate-spin" />
        )}
        <div className="flex-1">
          <div className={cn("text-sm font-semibold", statusColor)}>
            {isDone ? "Job complete" : job.status === "pending" ? "Job queued…" : "Processing resumes…"}
          </div>
          <div className="text-xs text-gray-400 font-mono mt-0.5">id: {job.job_id.slice(0, 8)}…</div>
        </div>
        {isDone && (
          <Button variant="ghost" size="sm" onClick={onReset} className="gap-1.5 text-purple-600 hover:bg-purple-100">
            <RefreshCw className="w-3.5 h-3.5" /> New batch
          </Button>
        )}
      </div>

      {/* Progress */}
      <div className="px-5 py-5 space-y-4">
        <div className="space-y-2">
          <Progress value={progressPct} />
          <div className="flex justify-between text-xs text-gray-500">
            <span>{progressPct}%</span>
            <span>{job.processed + job.failed} / {job.total}</span>
          </div>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-3 gap-3">
          <StatCard label="Total" value={job.total} />
          <StatCard label="Processed" value={job.processed} accent />
          <StatCard label="Failed" value={job.failed} error={job.failed > 0} />
        </div>

        {/* Error log */}
        {job.errors.length > 0 && (
          <div>
            <button
              onClick={onToggleErrors}
              className="flex items-center gap-1.5 text-xs font-medium text-amber-600 hover:text-amber-700 transition-colors"
            >
              <AlertCircle className="w-3.5 h-3.5" />
              {job.errors.length} file{job.errors.length !== 1 ? "s" : ""} had issues
              {showErrors ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
            </button>
            {showErrors && (
              <div className="mt-2 rounded-lg border border-amber-100 bg-amber-50 divide-y divide-amber-100 max-h-40 overflow-y-auto">
                {job.errors.map((e, i) => (
                  <div key={i} className="px-3 py-2">
                    <div className="text-xs font-medium text-amber-800 truncate">{e.file}</div>
                    <div className="text-xs text-amber-600 mt-0.5">{e.error}</div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

function StatCard({ label, value, accent, error }: { label: string; value: number; accent?: boolean; error?: boolean }) {
  return (
    <div className={cn(
      "rounded-lg px-3 py-2.5 text-center",
      accent ? "bg-purple-50" : error && value > 0 ? "bg-red-50" : "bg-gray-50"
    )}>
      <div className={cn(
        "text-xl font-semibold",
        accent ? "text-purple-700" : error && value > 0 ? "text-red-600" : "text-gray-700"
      )}>
        {value}
      </div>
      <div className="text-xs text-gray-400 mt-0.5">{label}</div>
    </div>
  )
}
