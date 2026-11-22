export type UserRole = "resident_owner" | "resident_renter" | "shophouse_guest" | "zone_manager"

export interface AuthUser {
  id: string
  name: string
  role: UserRole
  roleCode: "L1" | "L2" | "L3" | "L4"
  zoneId: string
  zoneName: string
  apartment?: string
  plateNumber?: string
}

export type AgreementStatus = "pending_confirmation" | "pending_approval" | "effective" | "rejected" | "expired"

export interface AgreementRecord {
  id: string
  zone_id: string
  booking_id: string
  zone_policy_id: string
  provider_user_id: string
  renter_user_id: string
  price_vnd: number
  body_rendered: string
  body_sha256: string
  status: AgreementStatus
  requires_approval: boolean
  confirm_deadline: string
  approval_request_id?: string | null
  provider_confirmed_at?: string | null
  renter_confirmed_at?: string | null
  effective_at?: string | null
  created_at: string
  updated_at: string
}

export interface AgreementOut {
  agreement: AgreementRecord
  body_sha256_hex: string
}

export interface GenerateAgreementOut {
  agreement: AgreementOut
  is_replay: boolean
  message: string
}

export interface SendOtpOut {
  agreement_id: string
  user_id: string
  role: "provider" | "renter" | string
  ttl_seconds: number
  dev_otp?: string | null
  message: string
}

export interface ConfirmAgreementIn {
  otp_code: string
  thread_id?: string | null
}

export interface ConsentRecordOut {
  id: string
  user_id: string
  action: string
  subject_type: string
  subject_id: string
  terms_version: string
  decision: string
  created_at: string
}

export interface ConfirmAgreementOut {
  agreement: AgreementOut
  consent_record: ConsentRecordOut
  role: string
  all_confirmed: boolean
  requires_approval: boolean
  message: string
}

export interface ParkingSlot {
  id: string
  code: string
  floor: "B1" | "B2" | "B3"
  kind: "TH1" | "TH2" | "TH3"
  pricePerHour: number
  isOccupied: boolean
  isBuffer: boolean
  nearLobby: string
  distanceMeters: number
  ownerApartment?: string
  sizeClass?: string
}

export interface RawSlotOut {
  id: string
  code: string
  floor: "B1" | "B2" | "B3"
  kind: "TH1" | "TH2" | "TH3"
  price_per_hour: number
  is_occupied: boolean
  is_buffer: boolean
  near_lobby: string
  distance_meters: number
  size_class: string
  owner_apartment?: string | null
}

export interface OwnerSchedule {
  slot_id: string
  slot_code: string
  owner_apartment: string
  active_days: string[]
  start_time: string
  end_time: string
  auto_share_lpr: boolean
  price_per_hour: number
  resident_share_percent: number
  daily_estimated_earnings: number
  monthly_estimated_earnings: number
  status: string
  current_booking_agreement?: string | null
  renter_plate_masked?: string | null
}

export interface EarlyReturnOut {
  success: boolean
  slot_code: string
  reallocated_slot_code: string
  reallocated_slot_id: string
  renter_refund_vnd: number
  message: string
}

export interface ApprovalItem {
  id: string
  code: string
  type: "high_value" | "early_return_swap" | "overstay_dispute" | "dimension_exception"
  title: string
  agreement_id: string
  slot_code: string
  renter_name: string
  plate_number: string
  price_vnd: number
  reason: string
  created_at_desc: string
  status: "pending" | "approved" | "rejected"
}
