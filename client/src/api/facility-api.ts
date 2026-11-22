import { apiClient } from "./client"
import type { ParkingSlot, RawSlotOut } from "@/types"

export const facilityApi = {
  getSlots: async (floor?: string, kind?: string): Promise<ParkingSlot[]> => {
    const params: Record<string, string> = {}
    if (floor) params.floor = floor
    if (kind) params.kind = kind

    const res = await apiClient.get<RawSlotOut[]>("/facility/slots", { params })
    return res.data.map((raw) => ({
      id: raw.id,
      code: raw.code,
      floor: raw.floor,
      kind: raw.kind,
      pricePerHour: raw.price_per_hour,
      isOccupied: raw.is_occupied,
      isBuffer: raw.is_buffer,
      nearLobby: raw.near_lobby,
      distanceMeters: raw.distance_meters,
      ownerApartment: raw.owner_apartment || undefined,
      sizeClass: raw.size_class,
    }))
  },
}
