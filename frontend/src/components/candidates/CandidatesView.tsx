import { useEffect, useState } from "react"
import { MapPin, GitFork, Link2, Trash2, ExternalLink, RefreshCw, Users } from "lucide-react"
import { listCandidates, deleteProfile, type Profile } from "@/api"
import { ProfileModal } from "@/components/ProfileModal"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

export function CandidatesView() {
  const [profiles, setProfiles] = useState<Profile[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedProfile, setSelectedProfile] = useState<Profile | null>(null)

  const load = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await listCandidates()
      setProfiles(data)
    } catch {
      setError("Failed to load candidates. Please try again.")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const handleDelete = (id: string) => {
    setProfiles((prev) => prev.filter((p) => p.id !== id))
  }

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="max-w-6xl mx-auto px-6 py-8">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-semibold text-gray-900 tracking-tight">Candidates</h1>
            <p className="text-sm text-gray-500 mt-1">
              {loading ? "Loading…" : `${profiles.length} candidate${profiles.length !== 1 ? "s" : ""} in your pool`}
            </p>
          </div>
          <Button variant="ghost" size="sm" onClick={load} disabled={loading} className="text-gray-500 gap-1.5">
            <RefreshCw className={cn("w-3.5 h-3.5", loading && "animate-spin")} /> Refresh
          </Button>
        </div>

        {/* Error */}
        {error && (
          <div className="rounded-lg bg-red-50 border border-red-100 px-4 py-3 text-sm text-red-600 mb-6">
            {error}
          </div>
        )}

        {/* Loading skeleton */}
        {loading && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {Array.from({ length: 8 }).map((_, i) => (
              <div key={i} className="rounded-xl border border-gray-100 bg-white p-4 animate-pulse">
                <div className="flex items-center gap-3 mb-3">
                  <div className="w-10 h-10 rounded-xl bg-gray-100 flex-none" />
                  <div className="flex-1 space-y-1.5">
                    <div className="h-3.5 bg-gray-100 rounded w-3/4" />
                    <div className="h-3 bg-gray-100 rounded w-1/2" />
                  </div>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {Array.from({ length: 3 }).map((_, j) => (
                    <div key={j} className="h-5 w-14 bg-gray-100 rounded-full" />
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Empty state */}
        {!loading && !error && profiles.length === 0 && (
          <div className="flex flex-col items-center justify-center py-24 text-center">
            <div className="w-14 h-14 rounded-2xl bg-purple-50 flex items-center justify-center mb-4">
              <Users className="w-7 h-7 text-purple-400" />
            </div>
            <h3 className="text-sm font-semibold text-gray-800">No candidates yet</h3>
            <p className="text-xs text-gray-400 mt-1 max-w-xs leading-relaxed">
              Upload resumes via Single Upload or Bulk Import to build your talent pool.
            </p>
          </div>
        )}

        {/* Grid */}
        {!loading && profiles.length > 0 && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {profiles.map((profile) => (
              <CandidateCard
                key={profile.id}
                profile={profile}
                onView={() => setSelectedProfile(profile)}
                onDeleted={() => handleDelete(profile.id)}
              />
            ))}
          </div>
        )}
      </div>

      <ProfileModal
        profile={selectedProfile}
        open={selectedProfile !== null}
        onClose={() => setSelectedProfile(null)}
      />
    </div>
  )
}

interface CardProps {
  profile: Profile
  onView: () => void
  onDeleted: () => void
}

function CandidateCard({ profile, onView, onDeleted }: CardProps) {
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [deleting, setDeleting] = useState(false)

  const handleDelete = async (e: React.MouseEvent) => {
    e.stopPropagation()
    if (!confirmDelete) {
      setConfirmDelete(true)
      setTimeout(() => setConfirmDelete(false), 3000)
      return
    }
    setDeleting(true)
    try {
      await deleteProfile(profile.id)
      onDeleted()
    } catch {
      setDeleting(false)
      setConfirmDelete(false)
    }
  }

  const initials = (profile.name ?? "?")[0].toUpperCase()

  return (
    <div className="group relative rounded-xl border border-gray-100 bg-white hover:border-purple-200 hover:shadow-sm transition-all duration-150 flex flex-col">
      {/* Card body */}
      <div className="p-4 flex-1">
        {/* Top row: avatar + delete */}
        <div className="flex items-start justify-between mb-3">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-xl bg-purple-100 flex items-center justify-center flex-none text-purple-700 font-semibold text-sm">
              {initials}
            </div>
            <div className="min-w-0">
              <div className="text-sm font-semibold text-gray-900 leading-tight truncate max-w-[120px]">
                {profile.name ?? "Unknown"}
              </div>
              {(profile.current_role || profile.current_company) && (
                <div className="text-[11px] text-gray-500 leading-tight truncate max-w-[120px]">
                  {[profile.current_role, profile.current_company].filter(Boolean).join(" · ")}
                </div>
              )}
            </div>
          </div>

          {/* Delete control */}
          <button
            onClick={handleDelete}
            disabled={deleting}
            className={cn(
              "flex-none flex items-center gap-1 rounded-md px-1.5 py-1 text-xs transition-all duration-150",
              confirmDelete
                ? "bg-red-50 text-red-600 border border-red-200"
                : "text-gray-300 hover:text-red-400 hover:bg-red-50 opacity-0 group-hover:opacity-100"
            )}
            title={confirmDelete ? "Click again to confirm delete" : "Delete candidate"}
          >
            <Trash2 className="w-3 h-3" />
            {confirmDelete && <span className="font-medium">Delete?</span>}
          </button>
        </div>

        {/* Headline */}
        {profile.headline && (
          <p className="text-xs text-gray-500 mb-2 leading-snug line-clamp-2">{profile.headline}</p>
        )}

        {/* Location */}
        {profile.location && (
          <div className="flex items-center gap-1 text-[11px] text-gray-400 mb-2.5">
            <MapPin className="w-3 h-3 flex-none" />
            <span className="truncate">{profile.location}</span>
          </div>
        )}

        {/* Skills */}
        {profile.skills?.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {profile.skills.slice(0, 5).map((s) => (
              <Badge key={s} variant="purple" className="text-[10px] px-1.5 py-0.5">{s}</Badge>
            ))}
            {profile.skills.length > 5 && (
              <Badge variant="gray" className="text-[10px] px-1.5 py-0.5">+{profile.skills.length - 5}</Badge>
            )}
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="px-4 pb-3 flex items-center justify-between">
        <div className="flex gap-2">
          {profile.source_urls?.github && (
            <a
              href={profile.source_urls.github}
              target="_blank"
              rel="noopener noreferrer"
              onClick={(e) => e.stopPropagation()}
              className="text-gray-300 hover:text-purple-600 transition-colors"
              title="GitHub"
            >
              <GitFork className="w-3.5 h-3.5" />
            </a>
          )}
          {profile.source_urls?.linkedin && (
            <a
              href={profile.source_urls.linkedin}
              target="_blank"
              rel="noopener noreferrer"
              onClick={(e) => e.stopPropagation()}
              className="text-gray-300 hover:text-purple-600 transition-colors"
              title="LinkedIn"
            >
              <Link2 className="w-3.5 h-3.5" />
            </a>
          )}
        </div>

        <button
          onClick={onView}
          className="flex items-center gap-1 text-[11px] text-purple-600 hover:text-purple-800 font-medium transition-colors"
        >
          <ExternalLink className="w-3 h-3" /> View
        </button>
      </div>
    </div>
  )
}
