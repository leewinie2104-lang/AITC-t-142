import { apiClient } from "@/api/client"
import type {
  AgreementOut,
  ConfirmAgreementIn,
  ConfirmAgreementOut,
  ConsentRecordOut,
  GenerateAgreementOut,
  SendOtpOut,
} from "@/types"

export const agreementApi = {
  /**
   * Lấy chi tiết văn bản thỏa thuận kèm mã băm SHA-256 (M6)
   */
  getAgreement: async (agreementId: string): Promise<AgreementOut> => {
    const res = await apiClient.get<AgreementOut>(`/agreements/${agreementId}`)
    return res.data
  },

  /**
   * Sinh thỏa thuận điện tử mới từ booking đã có (hoặc replay thỏa thuận cũ nếu đã sinh)
   */
  generateAgreement: async (bookingId: string): Promise<GenerateAgreementOut> => {
    const res = await apiClient.post<GenerateAgreementOut>("/agreements/generate", {
      booking_id: bookingId,
    })
    return res.data
  },

  /**
   * Phát sinh và gửi mã OTP qua Redis tới bên ký (renter hoặc provider)
   */
  sendOtp: async (agreementId: string, role?: string): Promise<SendOtpOut> => {
    const res = await apiClient.post<SendOtpOut>(
      `/agreements/${agreementId}/otp/send`,
      role ? { role } : {}
    )
    return res.data
  },

  /**
   * Xác nhận thỏa thuận bằng mã OTP và ghi log chấp thuận (consent_record)
   */
  confirmAgreement: async (
    agreementId: string,
    payload: ConfirmAgreementIn
  ): Promise<ConfirmAgreementOut> => {
    const res = await apiClient.post<ConfirmAgreementOut>(
      `/agreements/${agreementId}/confirm`,
      payload
    )
    return res.data
  },

  /**
   * Xem danh sách bằng chứng xác nhận đồng ý bất biến (app.consent_record)
   */
  getConsentRecords: async (agreementId: string): Promise<ConsentRecordOut[]> => {
    const res = await apiClient.get<ConsentRecordOut[]>(
      `/agreements/${agreementId}/consent-records`
    )
    return res.data
  },
}
