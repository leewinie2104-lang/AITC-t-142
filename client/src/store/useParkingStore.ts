import { create } from "zustand"
import type { AgreementRecord, ParkingSlot } from "@/types"

interface ParkingState {
  slots: ParkingSlot[]
  selectedSlot: ParkingSlot | null
  activeAgreement: AgreementRecord | null
  setSlots: (slots: ParkingSlot[]) => void
  setSelectedSlot: (slot: ParkingSlot | null) => void
  setActiveAgreement: (agreement: AgreementRecord | null) => void
}

export const useParkingStore = create<ParkingState>((set) => ({
  slots: [],
  selectedSlot: null,
  activeAgreement: null,
  setSlots: (slots) =>
    set((state) => ({
      slots,
      selectedSlot:
        (state.selectedSlot && slots.find((s) => s.code === state.selectedSlot?.code)) ||
        slots[0] ||
        null,
    })),
  setSelectedSlot: (slot) => set({ selectedSlot: slot }),
  setActiveAgreement: (agreement) => set({ activeAgreement: agreement }),
}))
