import { useState } from "react"
import { AuthProvider, useAuth } from "@/contexts/AuthContext"
import { Layout, type View } from "@/components/Layout"
import { SingleUpload } from "@/components/upload/SingleUpload"
import { BulkUpload } from "@/components/upload/BulkUpload"
import { SearchChat } from "@/components/search/SearchChat"
import { CandidatesView } from "@/components/candidates/CandidatesView"
import { LoginPage } from "@/pages/LoginPage"

function AppContent() {
  const { user, loading } = useAuth()
  const [view, setView] = useState<View>("search")

  if (loading) {
    return (
      <div className="min-h-screen bg-white flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-purple-700 flex items-center justify-center">
            <svg className="w-4 h-4 text-white animate-pulse" fill="currentColor" viewBox="0 0 24 24">
              <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" />
            </svg>
          </div>
          <span className="text-sm text-gray-400">Loading…</span>
        </div>
      </div>
    )
  }

  if (!user) {
    return <LoginPage />
  }

  return (
    <Layout view={view} onView={setView}>
      {view === "upload" && <SingleUpload />}
      {view === "bulk" && <BulkUpload />}
      {view === "search" && <SearchChat />}
      {view === "candidates" && <CandidatesView />}
    </Layout>
  )
}

function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  )
}

export default App
