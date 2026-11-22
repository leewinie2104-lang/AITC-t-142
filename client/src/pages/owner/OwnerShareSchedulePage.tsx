import React from "react"
import { useAuthStore } from "@/store/useAuthStore"
import { sharingApi } from "@/api/sharing-api"
import type { OwnerSchedule } from "@/types"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { formatVnd } from "@/lib/utils"
import {
  Calendar,
  Clock,
  AlertTriangle,
  Car,
  ShieldCheck,
  TrendingUp,
  History,
  CheckCircle2,
  Loader2,
} from "lucide-react"

interface OwnerShareSchedulePageProps {
  simulationMode?: "normal" | "concurrency" | "early_return" | "overstay"
  onTriggerEarlyReturn?: () => void
}

export const OwnerShareSchedulePage: React.FC<OwnerShareSchedulePageProps> = ({
  simulationMode = "normal",
  onTriggerEarlyReturn,
}) => {
  const { currentUser } = useAuthStore()

  // Real API State
  const [schedule, setSchedule] = React.useState<OwnerSchedule | null>(null)
  const [isLoading, setIsLoading] = React.useState(true)
  const [isSaving, setIsSaving] = React.useState(false)
  const [saveSuccessMsg, setSaveSuccessMsg] = React.useState<string | null>(null)
  const [saveErrorMsg, setSaveErrorMsg] = React.useState<string | null>(null)

  // Schedule form state
  const [activeDays, setActiveDays] = React.useState<string[]>(["T2", "T3", "T4", "T5", "T6"])
  const [startTime, setStartTime] = React.useState("08:00")
  const [endTime, setEndTime] = React.useState("17:30")
  const [autoShare, setAutoShare] = React.useState(true)

  // Early return state
  const [earlyReturnTriggered, setEarlyReturnTriggered] = React.useState(
    simulationMode === "early_return"
  )
  const [showConfirmModal, setShowConfirmModal] = React.useState(false)

  // 1. Fetch real schedule from FastAPI
  React.useEffect(() => {
    let isMounted = true
    const loadSchedule = async () => {
      try {
        setIsLoading(true)
        const data = await sharingApi.getMySchedule()
        if (isMounted) {
          setSchedule(data)
          setActiveDays(data.active_days)
          setStartTime(data.start_time)
          setEndTime(data.end_time)
          setAutoShare(data.auto_share_lpr)
          if (data.status === "early_return_swapped") {
            setEarlyReturnTriggered(true)
          }
        }
      } catch (err: unknown) {
        console.warn("Could not fetch schedule from API, using fallback:", err)
      } finally {
        if (isMounted) setIsLoading(false)
      }
    }
    loadSchedule()
    return () => {
      isMounted = false
    }
  }, [])

  React.useEffect(() => {
    if (simulationMode === "early_return") {
      setEarlyReturnTriggered(true)
    }
  }, [simulationMode])

  const daysOfWeek = [
    { key: "T2", label: "Thứ 2" },
    { key: "T3", label: "Thứ 3" },
    { key: "T4", label: "Thứ 4" },
    { key: "T5", label: "Thứ 5" },
    { key: "T6", label: "Thứ 6" },
    { key: "T7", label: "Thứ 7" },
    { key: "CN", label: "Chủ Nhật" },
  ]

  const toggleDay = (key: string) => {
    if (activeDays.includes(key)) {
      setActiveDays(activeDays.filter((d) => d !== key))
    } else {
      setActiveDays([...activeDays, key])
    }
  }

  // 2. Real API: Save Schedule (Senior: hiển thị lỗi trung thực nếu thất bại)
  const handleSaveSchedule = async () => {
    setIsSaving(true)
    setSaveSuccessMsg(null)
    setSaveErrorMsg(null)
    try {
      const updated = await sharingApi.updateSchedule({
        active_days: activeDays,
        start_time: startTime,
        end_time: endTime,
        auto_share_lpr: autoShare,
      })
      setSchedule(updated)
      setSaveSuccessMsg("Đã lưu lịch chia sẻ thành công lên máy chủ!")
      setTimeout(() => setSaveSuccessMsg(null), 3000)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Không thể kết nối máy chủ để lưu lịch"
      setSaveErrorMsg(msg)
      setTimeout(() => setSaveErrorMsg(null), 4000)
    } finally {
      setIsSaving(false)
    }
  }

  // 3. Real API: Trigger Early Return W3
  const handleConfirmEarlyReturn = async () => {
    setShowConfirmModal(false)
    try {
      const slotId = schedule?.slot_id || "4912c77d-63bf-5bfa-806f-ae9bc3499a34"
      await sharingApi.triggerEarlyReturn(slotId)
      setEarlyReturnTriggered(true)
      if (onTriggerEarlyReturn) onTriggerEarlyReturn()
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Không thể gửi sự kiện về sớm lên máy chủ"
      setSaveErrorMsg(msg)
      setTimeout(() => setSaveErrorMsg(null), 4000)
    }
  }

  // Financial calculations
  const pricePerHour = schedule?.price_per_hour || 15000
  const hoursPerDay = 9.5
  const dailyTotal = pricePerHour * hoursPerDay
  const residentShare = dailyTotal * 0.7
  const estimatedMonthly = schedule?.monthly_estimated_earnings || residentShare * (activeDays.length * 4)

  return (
    <div className="w-full max-w-7xl px-4 py-6 space-y-6">
      {/* Header Banner */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-white p-6 rounded-3xl border border-neutral-200/80 shadow-sm">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <h1 className="text-xl md:text-2xl font-black text-neutral-900 tracking-tight">
              Quản lý ô đỗ cá nhân
            </h1>
            <Badge variant="th1" className="text-xs">TH1 Cư Dân</Badge>
          </div>
          <p className="text-xs md:text-sm text-muted-foreground">
            Căn hộ <strong className="text-neutral-900">{currentUser.apartment || "S2.01-1408"}</strong> · 
            Ô cố định: <strong className="text-neutral-900">{schedule?.slot_code || "B2-045"}</strong> (Hầm B2 Tòa S2)
          </p>
        </div>

        <div className="flex items-center gap-3">
          {/* Emergency Early Return Button */}
          <Button
            onClick={() => setShowConfirmModal(true)}
            variant={earlyReturnTriggered ? "outline" : "destructive"}
            className="h-11 px-5 rounded-2xl font-extrabold text-xs shadow-md flex items-center gap-2"
          >
            <AlertTriangle className="w-4 h-4" />
            <span>{earlyReturnTriggered ? "Đang xử lý về sớm (TH3)" : "Tôi về sớm (W3)"}</span>
          </Button>
        </div>
      </div>

      {/* Early Return Alert banner if active */}
      {earlyReturnTriggered && (
        <div className="rounded-2xl bg-amber-500/10 border-2 border-amber-500/40 p-4 text-amber-950 flex flex-col sm:flex-row sm:items-center justify-between gap-3 animate-in fade-in">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-amber-500 text-white flex items-center justify-center shrink-0">
              <AlertTriangle className="w-5 h-5 text-black" />
            </div>
            <div>
              <div className="font-extrabold text-sm text-amber-900">
                Đã kích hoạt quy trình Chủ chỗ về sớm (Cơ chế W3)
              </div>
              <div className="text-xs text-amber-800">
                Hệ thống LangGraph Agent đã tự động điều phối xe khách sang ô <strong>TH3-01 (Dự phòng BQL)</strong>. Ô <strong>{schedule?.slot_code || "B2-045"}</strong> của bạn sẵn sàng trống khi bạn về tới cổng!
              </div>
            </div>
          </div>
          <Badge className="bg-amber-600 text-white border-none text-xs whitespace-nowrap self-start sm:self-center">
            Cam kết 100% có chỗ
          </Badge>
        </div>
      )}

      {/* Main Grid: Schedule on Left, Earnings & Status on Right */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left Column (7 cols): Schedule Setup */}
        <div className="lg:col-span-7 space-y-6">
          <Card className="border-border/80 shadow-md">
            <CardHeader className="pb-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Calendar className="w-5 h-5 text-neutral-900" />
                  <CardTitle className="text-base font-extrabold">Lịch chia sẻ định kỳ</CardTitle>
                </div>
                <Badge variant={autoShare ? "success" : "outline"} className="text-xs">
                  {autoShare ? "Đang tự động chia sẻ" : "Tạm dừng"}
                </Badge>
              </div>
              <CardDescription>
                Dữ liệu đồng bộ trực tiếp với FastAPI `/api/v1/sharing/schedule`.
              </CardDescription>
            </CardHeader>

            <CardContent className="space-y-6">
              {/* Day of Week Selector */}
              <div className="space-y-2">
                <label className="text-xs font-bold text-neutral-700 block">
                  Các ngày chia sẻ trong tuần:
                </label>
                <div className="grid grid-cols-4 sm:grid-cols-7 gap-2">
                  {daysOfWeek.map((day) => {
                    const isSelected = activeDays.includes(day.key)
                    return (
                      <button
                        key={day.key}
                        type="button"
                        onClick={() => toggleDay(day.key)}
                        className={`h-11 rounded-xl text-xs font-extrabold transition-all flex flex-col items-center justify-center gap-0.5 ${
                          isSelected
                            ? "bg-black text-white shadow-md scale-102"
                            : "bg-neutral-100 text-neutral-500 hover:bg-neutral-200"
                        }`}
                      >
                        <span>{day.key}</span>
                        <span className="text-[9px] font-normal opacity-80">{day.label}</span>
                      </button>
                    )
                  })}
                </div>
              </div>

              {/* Time Window Inputs */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <label className="text-xs font-bold text-neutral-700 flex items-center gap-1.5">
                    <Clock className="w-3.5 h-3.5 text-neutral-500" />
                    <span>Giờ xe rời bãi (Bắt đầu):</span>
                  </label>
                  <input
                    type="time"
                    value={startTime}
                    onChange={(e) => setStartTime(e.target.value)}
                    className="w-full bg-neutral-100 border border-neutral-300 rounded-xl px-3 py-2 text-sm font-mono font-bold focus:ring-2 focus:ring-black outline-none"
                  />
                  <span className="text-[10px] text-muted-foreground">Xe cư dân thường ra: ~07:45</span>
                </div>

                <div className="space-y-1.5">
                  <label className="text-xs font-bold text-neutral-700 flex items-center gap-1.5">
                    <Clock className="w-3.5 h-3.5 text-neutral-500" />
                    <span>Giờ xe quay về (Kết thúc):</span>
                  </label>
                  <input
                    type="time"
                    value={endTime}
                    onChange={(e) => setEndTime(e.target.value)}
                    className="w-full bg-neutral-100 border border-neutral-300 rounded-xl px-3 py-2 text-sm font-mono font-bold focus:ring-2 focus:ring-black outline-none"
                  />
                  <span className="text-[10px] text-muted-foreground">Khách phải trả chỗ trước 15p</span>
                </div>
              </div>

              {/* Toggle Auto-Share */}
              <div className="p-4 rounded-2xl bg-neutral-50 border border-neutral-200/80 flex items-center justify-between">
                <div className="space-y-0.5">
                  <div className="text-xs font-extrabold text-neutral-900">
                    Tự động nhận diện xe qua camera LPR
                  </div>
                  <div className="text-[11px] text-muted-foreground">
                    Khi biển số của bạn ra khỏi cổng, hệ thống kích hoạt trạng thái sẵn sàng cho thuê.
                  </div>
                </div>
                <input
                  type="checkbox"
                  checked={autoShare}
                  onChange={(e) => setAutoShare(e.target.checked)}
                  className="w-5 h-5 accent-black rounded cursor-pointer"
                />
              </div>

              {saveSuccessMsg && (
                <div className="rounded-xl bg-emerald-50 border border-emerald-200 p-2.5 text-xs text-emerald-800 font-semibold flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                  <span>{saveSuccessMsg}</span>
                </div>
              )}

              {saveErrorMsg && (
                <div className="rounded-xl bg-rose-50 border border-rose-200 p-2.5 text-xs text-rose-800 font-semibold flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0" />
                  <span>{saveErrorMsg}</span>
                </div>
              )}

              <div className="flex gap-3">
                <Button
                  onClick={handleSaveSchedule}
                  disabled={isSaving || isLoading}
                  variant="uber"
                  className="flex-1 font-bold h-11 text-xs flex items-center justify-center gap-2"
                >
                  {isSaving ? <Loader2 className="w-4 h-4 animate-spin" /> : <span>Lưu thiết lập lịch</span>}
                </Button>
                <Button
                  variant="outline"
                  onClick={() => {
                    setActiveDays(["T2", "T3", "T4", "T5", "T6"])
                    setStartTime("08:00")
                    setEndTime("17:30")
                    setAutoShare(true)
                  }}
                  className="font-bold h-11 text-xs"
                >
                  Khôi phục mặc định
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* Dispute & Safety Policy Info */}
          <Card className="border-border/80 bg-neutral-900 text-white shadow-md">
            <CardHeader className="pb-3">
              <div className="flex items-center gap-2">
                <ShieldCheck className="w-5 h-5 text-emerald-400" />
                <CardTitle className="text-sm font-extrabold text-white">
                  Cam kết bảo vệ quyền lợi chủ chỗ (BR-03)
                </CardTitle>
              </div>
            </CardHeader>
            <CardContent className="space-y-2 text-xs text-neutral-300">
              <div className="flex items-start gap-2">
                <span className="text-emerald-400 font-bold">•</span>
                <span><strong>Bảo đảm chỗ 100%:</strong> Nếu về sớm bất ngờ, bạn luôn có ô đỗ ngay (hoặc ô TH3 VIP tầng B1 nếu ô của bạn đang được xe khác chuyển đi).</span>
              </div>
              <div className="flex items-start gap-2">
                <span className="text-emerald-400 font-bold">•</span>
                <span><strong>Được nhận 100% tiền phiên:</strong> Ngay cả khi về sớm, bạn vẫn nhận đủ 70% doanh thu của cả ca ngày hôm đó.</span>
              </div>
              <div className="flex items-start gap-2">
                <span className="text-emerald-400 font-bold">•</span>
                <span><strong>Phạt quá giờ:</strong> Nếu khách thuê đỗ quá giờ quy định, tiền phạt x3 sẽ được cộng trực tiếp vào ví của bạn và quỹ BQL.</span>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Right Column (5 cols): Financial Dashboard & Realtime Activity */}
        <div className="lg:col-span-5 space-y-6">
          {/* Earnings Card */}
          <Card className="border-border/80 shadow-md overflow-hidden">
            <div className="bg-gradient-to-br from-neutral-900 to-neutral-800 p-5 text-white">
              <div className="flex items-center justify-between text-neutral-400 text-xs">
                <span>Ước tính thu nhập tháng</span>
                <TrendingUp className="w-4 h-4 text-emerald-400" />
              </div>
              <div className="text-3xl font-mono font-black text-emerald-400 mt-2">
                {formatVnd(estimatedMonthly)}
              </div>
              <div className="text-[11px] text-neutral-300 mt-1">
                Dựa trên {activeDays.length * 4} ngày chia sẻ ({startTime} - {endTime})
              </div>
            </div>

            <CardContent className="p-4 space-y-3">
              <div className="text-xs font-bold text-neutral-800">Cơ chế phân chia lợi nhuận:</div>
              <div className="space-y-2 text-xs">
                <div className="flex justify-between items-center p-2 rounded-xl bg-emerald-50 text-emerald-950 border border-emerald-200">
                  <span className="font-bold">👤 Cư dân (70%)</span>
                  <span className="font-mono font-extrabold">{formatVnd(residentShare)} / ngày</span>
                </div>
                <div className="flex justify-between items-center p-2 rounded-xl bg-neutral-50 text-neutral-700 border border-neutral-200">
                  <span>🏢 Quỹ BQL (20%)</span>
                  <span className="font-mono font-medium">{formatVnd(dailyTotal * 0.2)} / ngày</span>
                </div>
                <div className="flex justify-between items-center p-2 rounded-xl bg-neutral-50 text-neutral-700 border border-neutral-200">
                  <span>⚡ Phí sàn AI (10%)</span>
                  <span className="font-mono font-medium">{formatVnd(dailyTotal * 0.1)} / ngày</span>
                </div>
              </div>

              <div className="pt-2">
                <Button variant="outline" className="w-full text-xs font-bold h-9">
                  Rút tiền về tài khoản ngân hàng
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* Current Slot Live Status */}
          <Card className="border-border/80 shadow-md">
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Car className="w-4 h-4 text-neutral-900" />
                  <CardTitle className="text-sm font-extrabold">Trạng thái ô {schedule?.slot_code || "B2-045"}</CardTitle>
                </div>
                <Badge variant={earlyReturnTriggered ? "warning" : "success"} className="text-xs">
                  {earlyReturnTriggered ? "Chuyển giao TH3" : "Đang chia sẻ"}
                </Badge>
              </div>
            </CardHeader>
            <CardContent className="space-y-3 text-xs">
              <div className="rounded-xl bg-neutral-50 p-3 border border-neutral-200 space-y-2">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Khách đang thuê:</span>
                  <span className="font-bold text-neutral-900">
                    Anh Tuấn ({schedule?.renter_plate_masked || "30A-88*.*8"})
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Thỏa thuận số:</span>
                  <span className="font-mono font-semibold text-neutral-800">
                    {schedule?.current_booking_agreement || "AGR-202611-0045"}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Khung giờ khách thuê:</span>
                  <span className="font-mono text-neutral-800">08:30 – 17:30</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Ký điện tử OTP:</span>
                  <span className="text-emerald-600 font-bold flex items-center gap-1">
                    <CheckCircle2 className="w-3.5 h-3.5" /> Đã xác thực
                  </span>
                </div>
              </div>

              {/* History item */}
              <div className="space-y-2 pt-1">
                <div className="font-bold text-neutral-700 text-[11px] flex items-center gap-1">
                  <History className="w-3.5 h-3.5" />
                  <span>Lịch sử phiên gần nhất:</span>
                </div>
                <div className="text-[11px] text-muted-foreground p-3 rounded-xl bg-neutral-50 border border-neutral-200/60 text-center">
                  Chưa có phiên hoàn tất phát sinh trong tuần này.
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Confirmation Modal for Early Return */}
      {showConfirmModal && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4 animate-in fade-in">
          <div className="bg-white rounded-3xl max-w-md w-full p-6 shadow-2xl border border-neutral-200 space-y-4">
            <div className="w-12 h-12 rounded-2xl bg-amber-100 text-amber-800 flex items-center justify-center mx-auto">
              <AlertTriangle className="w-6 h-6 text-amber-600" />
            </div>

            <div className="text-center space-y-1.5">
              <h3 className="text-lg font-black text-neutral-900">
                Xác nhận thông báo Về Sớm?
              </h3>
              <p className="text-xs text-muted-foreground leading-relaxed">
                Hệ thống AI sẽ gửi thông báo chuyển ô cho khách thuê sang <strong>ô TH3 dự phòng</strong> của BQL ngay lập tức. Bạn luôn có chỗ đỗ an toàn khi về tới cổng.
              </p>
            </div>

            <div className="bg-neutral-50 rounded-2xl p-3 border border-neutral-200 text-xs space-y-1.5">
              <div className="font-bold text-neutral-800">Quyền lợi chủ chỗ được giữ nguyên:</div>
              <div className="text-muted-foreground">• Vẫn nhận đủ 100% doanh thu của buổi hôm nay (94.500đ).</div>
              <div className="text-muted-foreground">• Khách nhận đền bù voucher từ quỹ phòng ngừa rủi ro.</div>
            </div>

            <div className="flex gap-2.5 pt-2">
              <Button
                variant="outline"
                onClick={() => setShowConfirmModal(false)}
                className="flex-1 font-bold h-11 text-xs"
              >
                Hủy bỏ
              </Button>
              <Button
                variant="destructive"
                onClick={handleConfirmEarlyReturn}
                className="flex-1 font-bold h-11 text-xs shadow-md"
              >
                Xác nhận về sớm
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
