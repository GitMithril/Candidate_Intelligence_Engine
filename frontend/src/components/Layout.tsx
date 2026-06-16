import { Upload, Users, MessageSquare, Zap } from "lucide-react"
import { cn } from "@/lib/utils"

export type View = "upload" | "bulk" | "search"

interface NavItem {
  id: View
  label: string
  icon: React.ComponentType<{ className?: string }>
  description: string
}

const NAV: NavItem[] = [
  { id: "upload", label: "Single Upload", icon: Upload, description: "One candidate" },
  { id: "bulk", label: "Bulk Import", icon: Users, description: "Up to 100 resumes" },
  { id: "search", label: "Search & Chat", icon: MessageSquare, description: "Find & converse" },
]

interface LayoutProps {
  view: View
  onView: (v: View) => void
  children: React.ReactNode
}

export function Layout({ view, onView, children }: LayoutProps) {
  return (
    <div className="flex h-screen bg-white overflow-hidden">
      {/* Sidebar */}
      <aside className="w-56 flex-none flex flex-col border-r border-gray-100 bg-white">
        {/* Brand */}
        <div className="h-14 flex items-center gap-2.5 px-5 border-b border-gray-100">
          <div className="w-7 h-7 rounded-lg bg-purple-700 flex items-center justify-center flex-none">
            <Zap className="w-3.5 h-3.5 text-white" />
          </div>
          <div>
            <div className="text-sm font-semibold text-gray-900 leading-none">TalentIQ</div>
            <div className="text-[10px] text-gray-400 leading-none mt-0.5">Intelligence System</div>
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
                  "w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-left transition-all duration-100 group",
                  active
                    ? "bg-purple-50 text-purple-700"
                    : "text-gray-600 hover:bg-gray-50 hover:text-gray-900"
                )}
              >
                <Icon
                  className={cn(
                    "w-4 h-4 flex-none transition-colors",
                    active ? "text-purple-600" : "text-gray-400 group-hover:text-gray-600"
                  )}
                />
                <div>
                  <div className={cn("text-sm font-medium leading-none", active ? "text-purple-700" : "")}>
                    {item.label}
                  </div>
                  <div className="text-[11px] text-gray-400 leading-none mt-1">
                    {item.description}
                  </div>
                </div>
                {active && (
                  <div className="ml-auto w-1 h-4 rounded-full bg-purple-500 flex-none" />
                )}
              </button>
            )
          })}
        </nav>

        {/* Footer */}
        <div className="p-4 border-t border-gray-100">
          <div className="text-[11px] text-gray-400 leading-relaxed">
            Powered by OpenRouter<br />
            Pinecone · MongoDB · Redis
          </div>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-hidden flex flex-col min-w-0">
        {children}
      </main>
    </div>
  )
}
