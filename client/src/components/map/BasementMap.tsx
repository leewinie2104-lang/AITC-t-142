import React from "react"
import { useParkingStore } from "@/store/useParkingStore"
import type { ParkingSlot } from "@/types"
import { Badge } from "@/components/ui/badge"

interface BasementMapProps {
  onSlotSelect?: (slot: ParkingSlot) => void
  disabled?: boolean
}

export const BasementMap: React.FC<BasementMapProps> = ({ onSlotSelect, disabled }) => {
  const { slots, selectedSlot, setSelectedSlot } = useParkingStore()
  const [activeFloor, setActiveFloor] = React.useState<"B1" | "B2" | "B3">("B2")

  // Senior: Dùng useMemo đánh chỉ mục slots theo code để O(1) lookup thay vì find() lặp lại
  const slotMap = React.useMemo(() => {
    const map = new Map<string, ParkingSlot>()
    for (const slot of slots) {
      map.set(slot.code, slot)
    }
    return map
  }, [slots])

  const slot43 = slotMap.get("B2-043") || slots[0]
  const slot45 = slotMap.get("B2-045") || slots[0]
  const slot46 = slotMap.get("B2-046") || slots[1] || slots[0]
  const slotTh3 = slots.find((s) => s.kind === "TH3") || slots[2] || slots[0]

  const handleSelect = (slot: ParkingSlot | undefined) => {
    if (!slot || disabled || slot.isOccupied) return
    setSelectedSlot(slot)
    onSlotSelect?.(slot)
  }

  return (
    <div className="relative w-full rounded-2xl bg-neutral-900 border border-neutral-800 overflow-hidden shadow-inner flex flex-col">
      {/* Map Header Controls */}
      <div className="p-3 sm:p-4 bg-neutral-900/90 border-b border-neutral-800 flex items-center justify-between z-10">
        <div className="flex items-center gap-2">
          <div className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse" />
          <span className="text-xs font-bold text-white tracking-wide">
            SƠ ĐỒ HẦM {activeFloor} · TÒA S2
          </span>
          <Badge variant="outline" className="text-[10px] text-neutral-400 border-neutral-700 hidden sm:inline">
            Live LPR Sensor
          </Badge>
        </div>

        {/* Floor Switcher */}
        <div className="flex rounded-lg bg-neutral-800 p-0.5 text-xs font-semibold">
          {(["B1", "B2", "B3"] as const).map((floor) => (
            <button
              key={floor}
              onClick={() => setActiveFloor(floor)}
              className={`px-2.5 py-1 rounded-md transition-all ${
                activeFloor === floor
                  ? "bg-white text-black font-bold shadow-sm"
                  : "text-neutral-400 hover:text-white"
              }`}
            >
              {floor}
            </button>
          ))}
        </div>
      </div>

      {/* SVG Map Canvas */}
      <div className="p-4 sm:p-6 flex items-center justify-center overflow-x-auto min-h-[300px] sm:min-h-[360px] bg-[#121316]">
        <svg viewBox="0 0 760 400" className="w-full max-w-2xl select-none drop-shadow-md">
          {/* Driving Lanes */}
          <rect x="20" y="20" width="720" height="360" rx="16" fill="#181a1f" stroke="#2d3139" strokeWidth="2" />
          <path d="M 80 140 L 680 140 M 80 260 L 680 260" stroke="#262a33" strokeWidth="36" strokeLinecap="round" />
          <path d="M 80 140 L 680 140 M 80 260 L 680 260" stroke="#404756" strokeWidth="2" strokeDasharray="12 12" />

          {/* Lobby S2 Elevator Core */}
          <g transform="translate(320, 170)">
            <rect width="120" height="60" rx="10" fill="#ea580c" fillOpacity="0.12" stroke="#ea580c" strokeWidth="1.5" />
            <text x="60" y="28" fill="#ffffff" fontSize="12" fontWeight="800" textAnchor="middle">
              SẢNH S2
            </text>
            <text x="60" y="44" fill="#fdba74" fontSize="9" fontWeight="600" textAnchor="middle">
              Thang máy cư dân
            </text>
            {/* Walking guideline to slot B2-045 */}
            <path d="M 0 30 Q -60 30 -60 -45" fill="none" stroke="#ea580c" strokeWidth="2.5" strokeDasharray="5 5" className="animate-pulse" />
          </g>

          {/* TOP ROW SLOTS (B2-041 to B2-048) */}
          {/* B2-041 (Occupied) */}
          <g transform="translate(60, 40)">
            <rect width="64" height="85" rx="6" fill="#262a33" stroke="#3b4252" strokeWidth="1.5" />
            <rect x="10" y="16" width="44" height="52" rx="6" fill="#4b5563" />
            <text x="32" y="78" fontSize="9" fontWeight="700" fill="#9ca3af" textAnchor="middle">B2-041</text>
          </g>

          {/* B2-042 (Occupied) */}
          <g transform="translate(140, 40)">
            <rect width="64" height="85" rx="6" fill="#262a33" stroke="#3b4252" strokeWidth="1.5" />
            <rect x="10" y="16" width="44" height="52" rx="6" fill="#374151" />
            <text x="32" y="78" fontSize="9" fontWeight="700" fill="#9ca3af" textAnchor="middle">B2-042</text>
          </g>

          {/* B2-043 (TH1 Available) - Fixed: chọn đúng slot43 */}
          <g
            onClick={() => handleSelect(slot43)}
            className="cursor-pointer group"
            transform="translate(220, 40)"
          >
            <rect
              width="64"
              height="85"
              rx="6"
              fill={selectedSlot?.code === "B2-043" ? "#ea580c" : "#064e3b"}
              stroke={selectedSlot?.code === "B2-043" ? "#fb923c" : "#059669"}
              strokeWidth="2"
              className="transition-colors group-hover:brightness-125"
            />
            <text x="32" y="24" fontSize="8" fontWeight="800" fill="#a7f3d0" textAnchor="middle">TH1</text>
            <text x="32" y="52" fontSize="9" fontWeight="800" fill="#ffffff" textAnchor="middle">15.000đ</text>
            <text x="32" y="76" fontSize="9" fontWeight="700" fill="#d1fae5" textAnchor="middle">B2-043</text>
          </g>

          <g
            onClick={() => handleSelect(slot45)}
            className="cursor-pointer group"
            transform="translate(300, 40)"
          >
            <rect
              width="64"
              height="85"
              rx="6"
              fill={selectedSlot?.code === "B2-045" ? "#000000" : "#064e3b"}
              stroke={selectedSlot?.code === "B2-045" ? "#ea580c" : "#059669"}
              strokeWidth="2.5"
              filter="drop-shadow(0 4px 10px rgba(234, 88, 12, 0.45))"
            />
            <rect x="6" y="8" width="52" height="15" rx="3" fill="#ea580c" />
            <text x="32" y="19" fontSize="8" fontWeight="800" fill="#ffffff" textAnchor="middle">GẦN SẢNH</text>
            <text x="32" y="50" fontSize="10" fontWeight="900" fill="#ea580c" textAnchor="middle">15.000đ</text>
            <text x="32" y="76" fontSize="10" fontWeight="800" fill="#ffffff" textAnchor="middle">B2-045</text>
          </g>

          {/* B2-046 (TH2 Comfort Large) */}
          <g
            onClick={() => handleSelect(slot46)}
            className="cursor-pointer group"
            transform="translate(380, 40)"
          >
            <rect
              width="64"
              height="85"
              rx="6"
              fill={selectedSlot?.code === "B2-046" ? "#ea580c" : "#064e3b"}
              stroke={selectedSlot?.code === "B2-046" ? "#fb923c" : "#059669"}
              strokeWidth="2"
              className="transition-colors group-hover:brightness-125"
            />
            <text x="32" y="24" fontSize="8" fontWeight="800" fill="#fed7aa" textAnchor="middle">TH2 (SUV)</text>
            <text x="32" y="52" fontSize="9" fontWeight="800" fill="#ffffff" textAnchor="middle">20.000đ</text>
            <text x="32" y="76" fontSize="9" fontWeight="700" fill="#d1fae5" textAnchor="middle">B2-046</text>
          </g>

          {/* B2-047 (Occupied) */}
          <g transform="translate(460, 40)">
            <rect width="64" height="85" rx="6" fill="#262a33" stroke="#3b4252" strokeWidth="1.5" />
            <rect x="10" y="16" width="44" height="52" rx="6" fill="#1f2937" />
            <text x="32" y="78" fontSize="9" fontWeight="700" fill="#9ca3af" textAnchor="middle">B2-047</text>
          </g>

          {/* TH3-01 & TH3-02 (Safety Buffer Pool - BQL Reserve) */}
          <g
            onClick={() => handleSelect(slotTh3)}
            className="cursor-pointer group"
            transform="translate(540, 40)"
          >
            <rect
              width="64"
              height="85"
              rx="6"
              fill={selectedSlot?.code === "TH3-01" ? "#4f46e5" : "#312e81"}
              stroke="#6366f1"
              strokeWidth="2"
              className="transition-colors group-hover:brightness-125"
            />
            <rect x="6" y="8" width="52" height="15" rx="3" fill="#6366f1" />
            <text x="32" y="19" fontSize="8" fontWeight="800" fill="#ffffff" textAnchor="middle">BUFFER 20%</text>
            <text x="32" y="52" fontSize="8" fontWeight="700" fill="#c7d2fe" textAnchor="middle">DỰ PHÒNG</text>
            <text x="32" y="76" fontSize="9" fontWeight="800" fill="#ffffff" textAnchor="middle">TH3-01</text>
          </g>

          <g transform="translate(620, 40)">
            <rect width="64" height="85" rx="6" fill="#312e81" stroke="#6366f1" strokeWidth="2" />
            <rect x="6" y="8" width="52" height="15" rx="3" fill="#6366f1" />
            <text x="32" y="19" fontSize="8" fontWeight="800" fill="#ffffff" textAnchor="middle">BUFFER 20%</text>
            <text x="32" y="52" fontSize="8" fontWeight="700" fill="#c7d2fe" textAnchor="middle">DỰ PHÒNG</text>
            <text x="32" y="76" fontSize="9" fontWeight="800" fill="#ffffff" textAnchor="middle">TH3-02</text>
          </g>

          {/* BOTTOM ROW SLOTS (B2-050 to B2-057) */}
          {[
            { id: "B2-050", kind: "TH1", price: "15k", available: true },
            { id: "B2-051", kind: "OCC", price: "", available: false },
            { id: "B2-052", kind: "OCC", price: "", available: false },
            { id: "B2-053", kind: "OCC", price: "", available: false },
            { id: "B2-054", kind: "OCC", price: "", available: false },
            { id: "B2-055", kind: "OCC", price: "", available: false },
            { id: "B2-056", kind: "OCC", price: "", available: false },
            { id: "B2-057", kind: "OCC", price: "", available: false },
          ].map((s, idx) => {
            const x = 60 + idx * 80
            return (
              <g key={s.id} transform={`translate(${x}, 280)`}>
                <rect
                  width="64"
                  height="85"
                  rx="6"
                  fill={s.available ? "#064e3b" : "#262a33"}
                  stroke={s.available ? "#059669" : "#3b4252"}
                  strokeWidth="1.5"
                />
                {!s.available && <rect x="10" y="16" width="44" height="52" rx="6" fill="#334155" />}
                {s.available && <text x="32" y="50" fontSize="9" fontWeight="800" fill="#34d399" textAnchor="middle">{s.price}</text>}
                <text x="32" y="76" fontSize="9" fontWeight="700" fill={s.available ? "#d1fae5" : "#9ca3af"} textAnchor="middle">
                  {s.id}
                </text>
              </g>
            )
          })}
        </svg>
      </div>

      {/* Map Footer Legend */}
      <div className="p-3 bg-neutral-900 border-t border-neutral-800 flex flex-wrap items-center justify-between gap-3 text-[11px] text-neutral-300">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-500" />
            <span>Trống (TH1/TH2 Cư dân)</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-indigo-500" />
            <span>TH3 Safety Buffer (20%)</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-neutral-600" />
            <span>Đã có xe</span>
          </div>
        </div>

        <div className="font-mono text-primary font-bold">
          Ô đang chọn: {selectedSlot ? `${selectedSlot.code} (${selectedSlot.kind})` : "Đang tải ô đỗ..."}
        </div>
      </div>
    </div>
  )
}
