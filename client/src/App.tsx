import React, { Suspense } from "react"
import { Navbar, NavigationTab } from "@/components/layout/Navbar"
import { AgentChatDrawer } from "@/components/agent/AgentChatDrawer"
import { RenterBookingView } from "@/pages/renter/RenterBookingView"
import { OwnerShareSchedulePage } from "@/pages/owner/OwnerShareSchedulePage"
import { AdminApprovalQueuePage } from "@/pages/admin/AdminApprovalQueuePage"
import { AgreementSigningPage } from "@/pages/renter/AgreementSigningPage"
import { useAuthStore } from "@/store/useAuthStore"

// Senior Performance: Lazy-load toolbar phát triển để loại khỏi critical bundle của production
const DevScenarioBar = React.lazy(() =>
  import("@/components/layout/DevScenarioBar").then((m) => ({ default: m.DevScenarioBar }))
)

export function App() {
  const { switchRole } = useAuthStore()
  const [activeTab, setActiveTab] = React.useState<NavigationTab>("renter")
  const [simulationMode, setSimulationMode] = React.useState<
    "normal" | "concurrency" | "early_return" | "overstay"
  >("normal")

  const handleSimulate = (mode: "normal" | "concurrency" | "early_return" | "overstay") => {
    setSimulationMode(mode)
    if (mode === "early_return") {
      setActiveTab("owner")
      switchRole("L1")
    } else if (mode === "concurrency" || mode === "overstay") {
      setActiveTab("renter")
      switchRole("L2")
    }
  }

  return (
    <div className="min-h-screen bg-neutral-50/50 flex flex-col antialiased selection:bg-neutral-900 selection:text-white">
      {/* 1. Development Edge-Case Scenario Toolbar (chỉ tải & render ở môi trường DEV) */}
      {import.meta.env.DEV && (
        <Suspense fallback={null}>
          <DevScenarioBar onSimulate={handleSimulate} />
        </Suspense>
      )}

      {/* 2. Main Navigation Header with Persona Switching */}
      <Navbar activeTab={activeTab} onSelectTab={setActiveTab} />

      {/* 3. Main Workspace Area */}
      <main className="flex-1 flex flex-col items-center">
        {activeTab === "renter" && <RenterBookingView simulationMode={simulationMode} />}
        {activeTab === "owner" && (
          <OwnerShareSchedulePage
            simulationMode={simulationMode}
            onTriggerEarlyReturn={() => setSimulationMode("early_return")}
          />
        )}
        {activeTab === "admin" && <AdminApprovalQueuePage />}
        {activeTab === "agreement_signing" && <AgreementSigningPage />}
      </main>

      {/* 4. Global Floating LangGraph Agent Copilot Drawer */}
      <AgentChatDrawer />

      {/* 5. Minimalist Footer */}
      <footer className="border-t border-border/40 py-4 text-center text-xs text-muted-foreground bg-white">
        <div className="max-w-7xl mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-2">
          <span>ParkSmart AI · Clean Architecture Frontend MVP</span>
          <span className="font-mono text-[11px] text-neutral-400">
            Postgres GiST · Redis OTP · LangGraph Bedrock · React 18 + Vite
          </span>
        </div>
      </footer>
    </div>
  )
}

export default App
