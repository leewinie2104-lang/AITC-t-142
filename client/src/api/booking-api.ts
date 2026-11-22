import { apiClient } from "./client"

export interface ParkingRequestIn {
  zone_id: string
  building_id: string
  requester_user_id: string
  vehicle_id: string
  vehicle_size: "S" | "M" | "L" | "XL" | string
  period_start: string
  period_end: string
  computed_level: "L1" | "L2" | "L3" | "L4" | string
  channel?: string
  idempotency_key: string
}

export interface BookingHeldOut {
  booking_id: string
  ref_no: number
  status: string
  hold_expires_at: string
}

export interface ParkingRequestOut {
  request_id: string
  outcome: string
  booking?: BookingHeldOut | null
  block_reason?: string | null
  message: string
}

export const bookingApi = {
  requestParking: async (payload: ParkingRequestIn): Promise<ParkingRequestOut> => {
    const res = await apiClient.post<ParkingRequestOut>("/bookings/request", payload)
    return res.data
  },
}
