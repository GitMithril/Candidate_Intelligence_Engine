import { useState } from "react"
import { SearchPanel } from "./SearchPanel"
import { ChatPanel } from "./ChatPanel"
import { ProfileModal } from "@/components/ProfileModal"
import type { Profile } from "@/api"

export function SearchChat() {
  const [selectedProfile, setSelectedProfile] = useState<Profile | null>(null)

  return (
    <div className="flex flex-1 overflow-hidden h-full">
      {/* Left — search */}
      <div className="w-[400px] flex-none border-r border-gray-100 flex flex-col overflow-hidden">
        <SearchPanel onSelectProfile={setSelectedProfile} />
      </div>

      {/* Right — chat */}
      <div className="flex-1 flex flex-col overflow-hidden min-w-0">
        <ChatPanel onSelectProfile={setSelectedProfile} />
      </div>

      {/* Profile modal (shared) */}
      <ProfileModal
        profile={selectedProfile}
        open={!!selectedProfile}
        onClose={() => setSelectedProfile(null)}
      />
    </div>
  )
}
