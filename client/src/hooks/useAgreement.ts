import { useMutation, useQueryClient } from "@tanstack/react-query"
import { agreementApi } from "@/api/agreement-api"
import type { ConfirmAgreementIn } from "@/types"

export const AGREEMENT_KEYS = {
  all: ["agreements"] as const,
  detail: (id: string) => [...AGREEMENT_KEYS.all, "detail", id] as const,
  consents: (id: string) => [...AGREEMENT_KEYS.all, "consents", id] as const,
}

export function useSendOtp() {
  return useMutation({
    mutationFn: ({ agreementId, role }: { agreementId: string; role?: string }) =>
      agreementApi.sendOtp(agreementId, role),
  })
}

export function useConfirmAgreement() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      agreementId,
      payload,
    }: {
      agreementId: string
      payload: ConfirmAgreementIn
    }) => agreementApi.confirmAgreement(agreementId, payload),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: AGREEMENT_KEYS.detail(variables.agreementId) })
      queryClient.invalidateQueries({ queryKey: AGREEMENT_KEYS.consents(variables.agreementId) })
    },
  })
}
