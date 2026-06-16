import { ExternalLink, GitFork, Link2, MapPin, Code2, GraduationCap, Briefcase } from "lucide-react"
import type { Profile } from "@/api"
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Badge } from "@/components/ui/badge"

interface ProfileModalProps {
  profile: Profile | null
  open: boolean
  onClose: () => void
}

export function ProfileModal({ profile, open, onClose }: ProfileModalProps) {
  if (!profile) return null

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader>
          <div className="flex items-start gap-4">
            {/* Avatar placeholder */}
            <div className="w-12 h-12 rounded-xl bg-purple-100 flex items-center justify-center flex-none text-purple-700 font-semibold text-lg">
              {(profile.name ?? "?")[0].toUpperCase()}
            </div>
            <div className="flex-1 min-w-0">
              <DialogTitle>{profile.name ?? "Unknown"}</DialogTitle>
              {profile.headline && (
                <p className="text-sm text-gray-500 mt-0.5 leading-snug">{profile.headline}</p>
              )}
              <div className="flex flex-wrap gap-3 mt-2">
                {profile.current_role && (
                  <span className="flex items-center gap-1 text-xs text-gray-500">
                    <Briefcase className="w-3 h-3" /> {profile.current_role}
                    {profile.current_company && ` · ${profile.current_company}`}
                  </span>
                )}
                {profile.location && (
                  <span className="flex items-center gap-1 text-xs text-gray-500">
                    <MapPin className="w-3 h-3" /> {profile.location}
                  </span>
                )}
              </div>
            </div>
          </div>

          {/* Links */}
          <div className="flex gap-2 mt-3 flex-wrap">
            {profile.source_urls?.github && (
              <a href={profile.source_urls.github} target="_blank" rel="noopener noreferrer"
                className="flex items-center gap-1.5 text-xs text-gray-600 hover:text-purple-700 border border-gray-200 hover:border-purple-200 rounded-md px-2.5 py-1.5 transition-colors">
                <GitFork className="w-3 h-3" /> GitHub <ExternalLink className="w-2.5 h-2.5" />
              </a>
            )}
            {profile.source_urls?.linkedin && (
              <a href={profile.source_urls.linkedin} target="_blank" rel="noopener noreferrer"
                className="flex items-center gap-1.5 text-xs text-gray-600 hover:text-purple-700 border border-gray-200 hover:border-purple-200 rounded-md px-2.5 py-1.5 transition-colors">
                <Link2 className="w-3 h-3" /> LinkedIn <ExternalLink className="w-2.5 h-2.5" />
              </a>
            )}
          </div>
        </DialogHeader>

        <div className="px-6 pb-6 mt-5 space-y-5">
          {/* Skills */}
          {profile.skills?.length > 0 && (
            <section>
              <SectionLabel icon={<Code2 className="w-3.5 h-3.5" />} label="Skills" />
              <div className="flex flex-wrap gap-1.5 mt-2">
                {profile.skills.slice(0, 30).map((s) => (
                  <Badge key={s} variant="purple">{s}</Badge>
                ))}
              </div>
            </section>
          )}

          {/* Experience */}
          {profile.experience?.length > 0 && (
            <section>
              <SectionLabel icon={<Briefcase className="w-3.5 h-3.5" />} label="Experience" />
              <div className="mt-2 space-y-3">
                {profile.experience.map((exp, i) => (
                  <div key={i} className="flex gap-3">
                    <div className="mt-1 w-1.5 h-1.5 rounded-full bg-purple-400 flex-none" />
                    <div>
                      <div className="text-sm font-medium text-gray-800 leading-snug">
                        {exp.title}
                        {exp.company && <span className="text-gray-500 font-normal"> · {exp.company}</span>}
                      </div>
                      {exp.duration && <div className="text-xs text-gray-400 mt-0.5">{exp.duration}</div>}
                      {exp.description && (
                        <p className="text-xs text-gray-500 mt-1 leading-relaxed line-clamp-3">
                          {exp.description}
                        </p>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* Education */}
          {profile.education?.length > 0 && (
            <section>
              <SectionLabel icon={<GraduationCap className="w-3.5 h-3.5" />} label="Education" />
              <div className="mt-2 space-y-2">
                {profile.education.map((edu, i) => (
                  <div key={i} className="flex gap-3">
                    <div className="mt-1 w-1.5 h-1.5 rounded-full bg-purple-400 flex-none" />
                    <div>
                      <div className="text-sm font-medium text-gray-800 leading-snug">{edu.school}</div>
                      <div className="text-xs text-gray-500">
                        {[edu.degree, edu.field].filter(Boolean).join(" · ")}
                        {edu.dates && <span className="text-gray-400"> · {edu.dates}</span>}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* GitHub stats */}
          {(profile.github_username || profile.total_contributions_90d) && (
            <section>
              <SectionLabel icon={<GitFork className="w-3.5 h-3.5" />} label="GitHub Activity" />
              <div className="mt-2 flex flex-wrap gap-3">
                {profile.total_contributions_90d != null && profile.total_contributions_90d > 0 && (
                  <Stat label="Contributions (90d)" value={String(profile.total_contributions_90d)} />
                )}
                {profile.top_languages?.slice(0, 4).map((l) => (
                  <Stat key={l.name} label={l.name} value={`${l.repo_count} repos`} />
                ))}
              </div>
              {profile.github_bio && (
                <p className="text-xs text-gray-500 mt-2 leading-relaxed">{profile.github_bio}</p>
              )}
            </section>
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}

function SectionLabel({ icon, label }: { icon: React.ReactNode; label: string }) {
  return (
    <div className="flex items-center gap-1.5 text-xs font-semibold text-gray-400 uppercase tracking-wider">
      {icon} {label}
    </div>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-gray-50 rounded-lg px-3 py-2">
      <div className="text-xs font-semibold text-gray-700">{value}</div>
      <div className="text-[11px] text-gray-400">{label}</div>
    </div>
  )
}
