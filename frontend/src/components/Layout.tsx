import { Upload, Users, MessageSquare, Zap, LayoutGrid, LogOut } from "lucide-react"
import { cn } from "@/lib/utils"
import { useAuth } from "@/contexts/AuthContext"

export type View = "upload" | "bulk" | "search" | "candidates"

interface NavItem {
  id: View
  label: string
  icon: React.ComponentType<{ className?: string }>
  description: string
}

const NAV: NavItem[] = [
  { id: "search",     label: "Search & Chat",  icon: MessageSquare, description: "Find & converse" },
  { id: "candidates", label: "Candidates",      icon: LayoutGrid,    description: "Your talent pool" },
  { id: "upload",     label: "Single Upload",   icon: Upload,        description: "One candidate" },
  { id: "bulk",       label: "Bulk Import",     icon: Users,         description: "Up to 100 resumes" },
]

interface LayoutProps {
  view: View
  onView: (v: View) => void
  children: React.ReactNode
}

export function Layout({ view, onView, children }: LayoutProps) {
  const { user, signOut } = useAuth()

  return (
    <div className="flex h-screen overflow-hidden bg-gray-50">
      {/* Sidebar — dark */}
      <aside className="w-56 flex-none flex flex-col border-r border-gray-800 bg-zinc-950">
        {/* Brand */}
        <div className="h-14 flex items-center gap-2.5 px-5 border-b border-gray-800">
          <div className="w-7 h-7 rounded-lg bg-purple-700 flex items-center justify-center flex-none shadow-lg shadow-purple-900/50">
            <Zap className="w-3.5 h-3.5 text-white" />
          </div>
          <div className="text-[11px] font-semibold text-white leading-none tracking-tight">
            Candidate Intelligence
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 p-3 space-y-0.5">
          {NAV.map((item) => {
            const Icon = item.icon
            const active = view === item.id
            return (
              <button
                key={item.id}
                onClick={() => onView(item.id)}
                className={cn(
                  "w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-left transition-all duration-100 group border",
                  active
                    ? "bg-purple-700/20 border-purple-700/30 text-purple-300"
                    : "text-gray-400 border-transparent hover:bg-zinc-800 hover:text-gray-100"
                )}
              >
                <Icon className={cn(
                  "w-4 h-4 flex-none transition-colors",
                  active ? "text-purple-400" : "text-gray-600 group-hover:text-gray-300"
                )} />
                <div>
                  <div className={cn(
                    "text-sm font-medium leading-none",
                    active ? "text-purple-300" : ""
                  )}>
                    {item.label}
                  </div>
                  <div className="text-[11px] text-gray-600 leading-none mt-1">{item.description}</div>
                </div>
                {active && <div className="ml-auto w-1 h-4 rounded-full bg-purple-500 flex-none" />}
              </button>
            )
          })}
        </nav>

        {/* Footer */}
        <div className="p-3 border-t border-gray-800 space-y-2">
          {user && (
            <div className="flex items-center gap-2.5 px-2 py-1.5">
              <div className="w-7 h-7 rounded-full bg-purple-900/70 flex items-center justify-center flex-none text-purple-300 text-xs font-semibold border border-purple-800/50">
                {(user.displayName ?? user.email ?? "U")[0].toUpperCase()}
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-xs font-medium text-gray-200 truncate">
                  {user.displayName ?? user.email?.split("@")[0]}
                </div>
                <div className="text-[10px] text-gray-600 truncate">{user.email}</div>
              </div>
            </div>
          )}
          <button
            onClick={signOut}
            className="w-full flex items-center gap-2 px-2 py-2 rounded-lg text-sm text-gray-500 hover:bg-red-950/30 hover:text-red-400 transition-colors group"
          >
            <LogOut className="w-3.5 h-3.5 text-gray-600 group-hover:text-red-400 transition-colors" />
            Sign out
          </button>
          <div className="text-[10px] text-gray-700 leading-relaxed px-2">
            Powered by OpenRouter<br />Pinecone · MongoDB · Redis
          </div>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-hidden flex flex-col min-w-0 bg-gray-50">
        {children}
      </main>
    </div>
  )
}
