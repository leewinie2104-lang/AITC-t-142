import { apiClient } from "./client"
import type { OwnerSchedule, EarlyReturnOut } from "@/types"

export interface UpdateSchedulePayload {
  active_days: string[]
  start_time: string
  end_time: string
  auto_share_lpr: boolean
}

export const sharingApi = {
  getMySchedule: async (): Promise<OwnerSchedule> => {
    const res = await apiClient.get<OwnerSchedule>("/sharing/my-schedule")
    return res.data
  },

  updateSchedule: async (payload: UpdateSchedulePayload): Promise<OwnerSchedule> => {
    const res = await apiClient.post<OwnerSchedule>("/sharing/schedule", payload)
    return res.data
  },

  triggerEarlyReturn: async (slotId: string, reason?: string): Promise<EarlyReturnOut> => {
    const res = await apiClient.post<EarlyReturnOut>("/sharing/early-return", {
      slot_id: slotId,
      reason: reason || "Chủ chỗ quay về sớm đột xuất",
    })
    return res.data
  },
}
