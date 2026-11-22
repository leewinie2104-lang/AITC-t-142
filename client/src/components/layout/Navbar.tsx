import { useAuthStore, DEV_ACCOUNTS } from "@/store/useAuthStore"
import { Badge } from "@/components/ui/badge"

export type NavigationTab = "renter" | "owner" | "admin" | "agreement_signing"

interface NavbarProps {
  activeTab: NavigationTab
  onSelectTab: (tab: NavigationTab) => void
}

export function Navbar({ activeTab, onSelectTab }: NavbarProps) {
  const { currentUser, switchRole } = useAuthStore()

  const handleRoleSwitch = (roleCode: "L1" | "L2" | "L4") => {
    switchRole(roleCode)
    if (roleCode === "L1") onSelectTab("owner")
    else if (roleCode === "L2") onSelectTab("renter")
    else if (roleCode === "L4") onSelectTab("admin")
  }

  return (
    <header className="sticky top-0 z-40 w-full border-b border-border/40 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="container flex h-16 max-w-7xl items-center justify-between px-4">
        {/* Brand Logo & Tabs */}
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-3 cursor-pointer" onClick={() => onSelectTab("renter")}>
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-neutral-900 via-neutral-950 to-orange-950 border border-orange-500/40 font-black text-white shadow-sm">
              <span className="text-primary font-black text-lg">P</span>
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-extrabold text-base tracking-tight text-neutral-900">
                  ParkSmart <span className="text-primary font-black">AI</span>
                </span>
                <span className="rounded-full bg-primary/10 border border-primary/20 px-2 py-0.5 text-[10px] font-extrabold text-primary">
                </span>
              </div>
              <p className="text-[11px] text-muted-foreground hidden sm:block">
                {currentUser.zoneName}
              </p>
            </div>
          </div>

          {/* Navigation Persona Tabs */}
          <nav className="hidden lg:flex items-center gap-1 bg-neutral-100 p-1 rounded-xl text-xs font-bold">
            <button
              onClick={() => {
                onSelectTab("renter")
                switchRole("L2")
              }}
              className={`px-3 py-1.5 rounded-lg transition-all ${
                activeTab === "renter"
                  ? "bg-white text-neutral-900 shadow-xs border border-neutral-200/60"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              🚗 Người thuê (L2)
            </button>
            <button
              onClick={() => {
                onSelectTab("owner")
                switchRole("L1")
              }}
              className={`px-3 py-1.5 rounded-lg transition-all ${
                activeTab === "owner"
                  ? "bg-white text-neutral-900 shadow-xs border border-neutral-200/60"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              🏠 Chủ chỗ (L1)
            </button>
            <button
              onClick={() => {
                onSelectTab("admin")
                switchRole("L4")
              }}
              className={`px-3 py-1.5 rounded-lg transition-all ${
                activeTab === "admin"
                  ? "bg-white text-neutral-900 shadow-xs border border-neutral-200/60"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              🏢 BQL Duyệt (L4)
            </button>
            <button
              onClick={() => onSelectTab("agreement_signing")}
              className={`px-3 py-1.5 rounded-lg transition-all ${
                activeTab === "agreement_signing"
                  ? "bg-white text-neutral-900 shadow-xs border border-neutral-200/60"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              📝 Ký số hợp đồng (M6)
            </button>
          </nav>
        </div>

        {/* Fast Role Switcher (Dành cho nội bộ Dev / Test) */}
        <div className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground font-medium hidden md:inline">
            Vai trò:
          </span>
          <div className="flex items-center rounded-xl bg-muted p-1">
            {DEV_ACCOUNTS.map((user) => (
              <button
                key={user.roleCode}
                onClick={() => handleRoleSwitch(user.roleCode as "L1" | "L2" | "L4")}
                className={`flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-xs font-bold transition-all ${
                  currentUser.roleCode === user.roleCode
                    ? "bg-white text-neutral-900 shadow-sm"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                <span>{user.roleCode}</span>
                <span className="hidden sm:inline">
                  {user.roleCode === "L1" ? "Chủ chỗ" : user.roleCode === "L2" ? "Người thuê" : "BQL"}
                </span>
              </button>
            ))}
          </div>

          <Badge variant="outline" className="font-mono text-xs hidden xl:flex">
            {currentUser.apartment || "VP Ban Quản Lý"}
          </Badge>
        </div>
      </div>

      {/* Mobile Tab bar */}
      <div className="flex lg:hidden overflow-x-auto px-4 py-2 border-t border-border/40 bg-neutral-50 gap-1 text-xs font-bold">
        <button
          onClick={() => {
            onSelectTab("renter")
            switchRole("L2")
          }}
          className={`px-2.5 py-1 rounded-lg shrink-0 ${
            activeTab === "renter" ? "bg-black text-white" : "text-muted-foreground"
          }`}
        >
          🚗 Người thuê
        </button>
        <button
          onClick={() => {
            onSelectTab("owner")
            switchRole("L1")
          }}
          className={`px-2.5 py-1 rounded-lg shrink-0 ${
            activeTab === "owner" ? "bg-black text-white" : "text-muted-foreground"
          }`}
        >
          🏠 Chủ chỗ
        </button>
        <button
          onClick={() => {
            onSelectTab("admin")
            switchRole("L4")
          }}
          className={`px-2.5 py-1 rounded-lg shrink-0 ${
            activeTab === "admin" ? "bg-black text-white" : "text-muted-foreground"
          }`}
        >
          🏢 BQL Duyệt
        </button>
        <button
          onClick={() => onSelectTab("agreement_signing")}
          className={`px-2.5 py-1 rounded-lg shrink-0 ${
            activeTab === "agreement_signing" ? "bg-black text-white" : "text-muted-foreground"
          }`}
        >
          📝 Ký số hợp đồng
        </button>
      </div>
    </header>
  )
}
