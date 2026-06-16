import { useState } from "react"
import { Layout, type View } from "@/components/Layout"
import { SingleUpload } from "@/components/upload/SingleUpload"
import { BulkUpload } from "@/components/upload/BulkUpload"
import { SearchChat } from "@/components/search/SearchChat"

function App() {
  const [view, setView] = useState<View>("search")

  return (
    <Layout view={view} onView={setView}>
      {view === "upload" && <SingleUpload />}
      {view === "bulk" && <BulkUpload />}
      {view === "search" && <SearchChat />}
    </Layout>
  )
}

export default App
