import { apiClient } from "./client"
import type { ApprovalItem } from "@/types"

export interface DecideApprovalPayload {
  decision: "approved" | "rejected"
  note?: string
}

export interface DecideApprovalResponse {
  id: string
  status: string
  decided_at: string
  message: string
}

export const approvalApi = {
  getApprovals: async (): Promise<ApprovalItem[]> => {
    const res = await apiClient.get<ApprovalItem[]>("/approvals")
    return res.data
  },

  decideApproval: async (
    id: string,
    payload: DecideApprovalPayload
  ): Promise<DecideApprovalResponse> => {
    const res = await apiClient.post<DecideApprovalResponse>(`/approvals/${id}/decide`, payload)
    return res.data
  },
}
