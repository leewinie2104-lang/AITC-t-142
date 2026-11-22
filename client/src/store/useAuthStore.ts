import { create } from "zustand"
import type { AuthUser } from "@/types"

// Danh sách tài khoản phát triển (dành cho kiểm thử nội bộ DEV)
export const DEV_ACCOUNTS: AuthUser[] = [
  {
    id: "00000000-0000-0000-0000-000000000002",
    name: "Trần Thị Renter (Người thuê)",
    role: "resident_renter",
    roleCode: "L2",
    zoneId: "00000000-0000-0000-0000-000000000010",
    zoneName: "Vinhomes Grand Park (Tòa S2)",
    apartment: "S2.05-1204",
    plateNumber: "30A-888.88",
  },
  {
    id: "00000000-0000-0000-0000-000000000001",
    name: "Nguyễn Văn Owner (Chủ nhà)",
    role: "resident_owner",
    roleCode: "L1",
    zoneId: "00000000-0000-0000-0000-000000000010",
    zoneName: "Vinhomes Grand Park (Tòa S2)",
    apartment: "S2.01-1408",
    plateNumber: "51K-999.99",
  },
  {
    id: "00000000-0000-0000-0000-000000000003",
    name: "Lê Văn Manager (Ban Quản Lý)",
    role: "zone_manager",
    roleCode: "L4",
    zoneId: "00000000-0000-0000-0000-000000000010",
    zoneName: "Vinhomes Grand Park (Tòa S2)",
  },
]

interface AuthState {
  currentUser: AuthUser
  setUser: (user: AuthUser) => void
  switchRole: (roleCode: "L1" | "L2" | "L4") => void
}

export const useAuthStore = create<AuthState>((set) => ({
  currentUser: DEV_ACCOUNTS[0],
  setUser: (user) => set({ currentUser: user }),
  switchRole: (roleCode) => {
    const user = DEV_ACCOUNTS.find((u) => u.roleCode === roleCode)
    if (user) set({ currentUser: user })
  },
}))
