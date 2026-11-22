import React from "react"
import { Badge } from "@/components/ui/badge"

interface DevScenarioBarProps {
  onSimulate: (mode: "normal" | "concurrency" | "early_return" | "overstay") => void
}

export const DevScenarioBar: React.FC<DevScenarioBarProps> = ({ onSimulate }) => {
  return (
    <div className="bg-neutral-900 border-b border-neutral-800 text-white px-4 py-2 text-xs flex flex-wrap items-center justify-between gap-2 z-40">
      <div className="flex items-center gap-2">
        <Badge variant="outline" className="border-emerald-500/50 bg-emerald-500/10 text-emerald-400 font-bold text-[10px] px-2 py-0.5">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 mr-1.5 animate-pulse" />
          DEV TEST TOOLBAR
        </Badge>
        <span className="text-neutral-400 hidden sm:inline">Kịch bản biên (Edge-case):</span>
      </div>

      <div className="flex items-center gap-1.5 flex-wrap">
        <button
          onClick={() => onSimulate("normal")}
          className="px-2.5 py-1 rounded-md bg-neutral-800 hover:bg-neutral-700 text-neutral-200 transition font-medium text-[11px]"
        >
          ⚡ 1. Chuẩn (Golden Path)
        </button>
        <button
          onClick={() => onSimulate("concurrency")}
          className="px-2.5 py-1 rounded-md bg-neutral-800 hover:bg-neutral-700 text-amber-300 transition font-medium text-[11px]"
        >
          ⚔️ 2. Tranh chấp (23P01)
        </button>
        <button
          onClick={() => onSimulate("early_return")}
          className="px-2.5 py-1 rounded-md bg-neutral-800 hover:bg-neutral-700 text-cyan-300 transition font-medium text-[11px]"
        >
          🔄 3. Chủ về sớm (TH3 Swap)
        </button>
        <button
          onClick={() => onSimulate("overstay")}
          className="px-2.5 py-1 rounded-md bg-neutral-800 hover:bg-neutral-700 text-rose-300 transition font-medium text-[11px]"
        >
          🚨 4. Quá giờ (Phạt x3)
        </button>
      </div>
    </div>
  )
}
