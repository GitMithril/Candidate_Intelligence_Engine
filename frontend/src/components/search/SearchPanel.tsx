import { useState } from "react"
import { Search, SlidersHorizontal, MapPin, Code2, Loader2, AlertCircle, Star } from "lucide-react"
import { searchProfiles, type Profile, type SearchResult } from "@/api"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"

interface SearchPanelProps {
  onSelectProfile: (p: Profile) => void
}

export function SearchPanel({ onSelectProfile }: SearchPanelProps) {
  const [query, setQuery] = useState("")
  const [skills, setSkills] = useState("")
  const [location, setLocation] = useState("")
  const [showFilters, setShowFilters] = useState(false)
  const [loading, setLoading] = useState(false)
  const [results, setResults] = useState<SearchResult[]>([])
  const [searched, setSearched] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSearch = async (e?: React.FormEvent) => {
    e?.preventDefault()
    if (!query.trim()) return
    setLoading(true)
    setError(null)
    try {
      const data = await searchProfiles(query, skills || undefined, location || undefined, 10)
      setResults(data.results)
      setSearched(true)
    } catch {
      setError("Search failed. Is the API running?")
    } finally {
      setLoading(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") handleSearch()
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="p-4 border-b border-gray-100 space-y-2.5">
        <div className="flex items-center gap-1 text-xs font-semibold text-gray-400 uppercase tracking-widest">
          <Search className="w-3 h-3" /> Semantic Search
        </div>

        {/* Main search */}
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-300 pointer-events-none" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Python developer with FastAPI experience…"
            className={cn(
              "w-full h-10 pl-9 pr-4 rounded-lg border bg-white text-sm text-gray-900 placeholder:text-gray-400",
              "border-gray-200 transition-all duration-150",
              "focus:border-purple-500 focus:outline-none focus:ring-2 focus:ring-purple-100"
            )}
          />
        </div>

        {/* Filter toggle */}
        <div className="flex items-center justify-between">
          <button
            onClick={() => setShowFilters((v) => !v)}
            className="flex items-center gap-1.5 text-xs text-gray-400 hover:text-gray-600 transition-colors"
          >
            <SlidersHorizontal className="w-3.5 h-3.5" />
            Filters
            {(skills || location) && (
              <span className="w-1.5 h-1.5 rounded-full bg-purple-500" />
            )}
          </button>
          <Button size="sm" onClick={() => handleSearch()} disabled={loading || !query.trim()}>
            {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : "Search"}
          </Button>
        </div>

        {/* Filters */}
        {showFilters && (
          <div className="space-y-2 pt-1">
            <div className="flex items-center gap-2">
              <Code2 className="w-3.5 h-3.5 text-gray-400 flex-none" />
              <Input
                value={skills}
                onChange={(e) => setSkills(e.target.value)}
                placeholder="python, react (comma-separated)"
                className="h-8 text-xs"
              />
            </div>
            <div className="flex items-center gap-2">
              <MapPin className="w-3.5 h-3.5 text-gray-400 flex-none" />
              <Input
                value={location}
                onChange={(e) => setLocation(e.target.value)}
                placeholder="Islamabad, Karachi…"
                className="h-8 text-xs"
              />
            </div>
          </div>
        )}
      </div>

      {/* Results */}
      <div className="flex-1 overflow-y-auto">
        {error && (
          <div className="m-4 flex items-center gap-2 text-xs text-red-500 bg-red-50 rounded-lg px-3 py-2.5">
            <AlertCircle className="w-3.5 h-3.5 flex-none" /> {error}
          </div>
        )}

        {!searched && !loading && (
          <div className="flex flex-col items-center justify-center h-full text-center px-6 py-12">
            <div className="w-10 h-10 rounded-xl bg-purple-50 flex items-center justify-center mb-3">
              <Search className="w-5 h-5 text-purple-400" />
            </div>
            <p className="text-sm text-gray-400 max-w-48 leading-relaxed">
              Search by skills, role, company, or describe what you need.
            </p>
          </div>
        )}

        {loading && (
          <div className="flex items-center justify-center py-12 gap-2 text-sm text-gray-400">
            <Loader2 className="w-4 h-4 animate-spin text-purple-400" /> Searching…
          </div>
        )}

        {searched && !loading && results.length === 0 && (
          <div className="text-center py-12 text-sm text-gray-400">
            No candidates matched your search.
          </div>
        )}

        {results.length > 0 && !loading && (
          <div className="divide-y divide-gray-50">
            {results.map(({ profile, score }) => (
              <CandidateCard
                key={profile.id}
                profile={profile}
                score={score}
                onClick={() => onSelectProfile(profile)}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function CandidateCard({ profile, score, onClick }: { profile: Profile; score: number; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="w-full text-left px-4 py-3.5 hover:bg-gray-50/80 transition-colors group"
    >
      <div className="flex items-start gap-3">
        {/* Avatar */}
        <div className="w-8 h-8 rounded-lg bg-purple-100 flex items-center justify-center flex-none text-purple-700 text-sm font-semibold">
          {(profile.name ?? "?")[0].toUpperCase()}
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between gap-2">
            <span className="text-sm font-medium text-gray-900 truncate group-hover:text-purple-700 transition-colors">
              {profile.name ?? "Unknown"}
            </span>
            <ScorePill score={score} />
          </div>

          {profile.headline && (
            <div className="text-xs text-gray-500 truncate mt-0.5 leading-snug">{profile.headline}</div>
          )}

          {(profile.current_role || profile.current_company) && !profile.headline && (
            <div className="text-xs text-gray-500 truncate mt-0.5">
              {[profile.current_role, profile.current_company].filter(Boolean).join(" · ")}
            </div>
          )}

          {profile.location && (
            <div className="flex items-center gap-1 text-xs text-gray-400 mt-0.5">
              <MapPin className="w-2.5 h-2.5" /> {profile.location}
            </div>
          )}

          {profile.skills?.length > 0 && (
            <div className="flex flex-wrap gap-1 mt-1.5">
              {profile.skills.slice(0, 4).map((s) => (
                <Badge key={s} variant="gray" className="text-[10px] px-1.5 py-0">{s}</Badge>
              ))}
              {profile.skills.length > 4 && (
                <Badge variant="gray" className="text-[10px] px-1.5 py-0">+{profile.skills.length - 4}</Badge>
              )}
            </div>
          )}
        </div>
      </div>
    </button>
  )
}

function ScorePill({ score }: { score: number }) {
  const pct = Math.round(score * 100)
  const good = pct >= 70
  return (
    <span className={cn(
      "flex items-center gap-0.5 text-[10px] font-mono font-medium px-1.5 py-0.5 rounded-md flex-none",
      good ? "bg-purple-50 text-purple-600" : "bg-gray-100 text-gray-500"
    )}>
      <Star className="w-2.5 h-2.5" />
      {pct}%
    </span>
  )
}
