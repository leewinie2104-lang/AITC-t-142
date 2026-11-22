import React from "react"
import { useAuthStore } from "@/store/useAuthStore"
import { approvalApi } from "@/api/approval-api"
import type { ApprovalItem } from "@/types"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { formatVnd } from "@/lib/utils"
import {
  Building2,
  CheckCircle2,
  XCircle,
  ShieldAlert,
  Clock,
  Layers,
  Check,
  X,
  FileText,
  Loader2,
  AlertTriangle,
} from "lucide-react"

export const AdminApprovalQueuePage: React.FC = () => {
  const { currentUser } = useAuthStore()

  // Real API State
  const [items, setItems] = React.useState<ApprovalItem[]>([])
  const [isLoading, setIsLoading] = React.useState(true)
  const [actionInProgress, setActionInProgress] = React.useState<string | null>(null)
  const [actionError, setActionError] = React.useState<string | null>(null)
  const [filterType, setFilterType] = React.useState<string>("all")

  // 1. Fetch real approvals from FastAPI on mount
  React.useEffect(() => {
    let isMounted = true
    const loadApprovals = async () => {
      try {
        setIsLoading(true)
        setActionError(null)
        const data = await approvalApi.getApprovals()
        if (isMounted) {
          setItems(data)
        }
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : "Không thể tải danh sách phê duyệt từ API"
        if (isMounted) {
          setActionError(msg)
        }
      } finally {
        if (isMounted) setIsLoading(false)
      }
    }
    loadApprovals()
    return () => {
      isMounted = false
    }
  }, [])

  // 2. Real API: Decide approval item (Senior: không nuốt lỗi, hiển thị feedback chính xác)
  const handleAction = async (id: string, action: "approved" | "rejected") => {
    setActionInProgress(id)
    setActionError(null)
    try {
      await approvalApi.decideApproval(id, { decision: action })
      setItems((prev) =>
        prev.map((item) => (item.id === id ? { ...item, status: action } : item))
      )
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Thao tác gửi quyết định phê duyệt thất bại"
      setActionError(`Lỗi xử lý yêu cầu ${id}: ${msg}. Vui lòng thử lại.`)
    } finally {
      setActionInProgress(null)
    }
  }

  const filteredItems = items.filter((item) => {
    if (filterType === "all") return true
    if (filterType === "pending") return item.status === "pending"
    return item.status === filterType
  })

  const pendingCount = items.filter((i) => i.status === "pending").length

  return (
    <div className="w-full max-w-7xl px-4 py-6 space-y-6">
      {/* Top Banner */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-white p-6 rounded-3xl border border-neutral-200/80 shadow-sm">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <h1 className="text-xl md:text-2xl font-black text-neutral-900 tracking-tight">
              Trung tâm Điều phối BQL Tòa Nhà
            </h1>
            <Badge variant="outline" className="font-mono text-xs bg-black text-white">
              L4 Admin
            </Badge>
          </div>
          <p className="text-xs md:text-sm text-muted-foreground">
            Khu đô thị: <strong className="text-neutral-900">{currentUser.zoneName}</strong> · 
            Đồng bộ dữ liệu thời gian thực từ FastAPI `/api/v1/approvals` (Milestone M12).
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Badge variant="outline" className="text-xs font-bold py-1 px-3 border-emerald-500/40 bg-emerald-50 text-emerald-800">
            <span className="w-2 h-2 rounded-full bg-emerald-500 mr-2 animate-pulse" />
            LPR CAMERA ONLINE (4/4 CỔNG)
          </Badge>
        </div>
      </div>

      {/* Global Error Banner */}
      {actionError && (
        <div className="rounded-2xl bg-rose-50 border border-rose-200 p-4 text-xs text-rose-800 flex items-center justify-between gap-3 animate-in fade-in">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0" />
            <span className="font-semibold">{actionError}</span>
          </div>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => setActionError(null)}
            className="h-7 text-[11px] text-rose-700 hover:bg-rose-100"
          >
            Đóng
          </Button>
        </div>
      )}

      {/* Capacity & Safety Buffer KPI Widgets */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* KPI 1: Occupancy */}
        <Card className="p-4 border-border/80 shadow-sm">
          <div className="flex items-center justify-between text-muted-foreground text-xs">
            <span>Tỷ lệ lấp đầy Hầm B2</span>
            <Layers className="w-4 h-4 text-neutral-600" />
          </div>
          <div className="text-2xl font-black text-neutral-900 mt-2 font-mono">
            82% <span className="text-xs font-normal text-muted-foreground">(98/120 ô)</span>
          </div>
          <div className="w-full bg-neutral-100 h-2 rounded-full mt-2 overflow-hidden">
            <div className="bg-neutral-900 h-full rounded-full" style={{ width: "82%" }} />
          </div>
        </Card>

        {/* KPI 2: TH3 Safety Buffer */}
        <Card className="p-4 border-border/80 shadow-sm">
          <div className="flex items-center justify-between text-muted-foreground text-xs">
            <span>Đệm an toàn BQL (TH3 Buffer)</span>
            <ShieldAlert className="w-4 h-4 text-emerald-600" />
          </div>
          <div className="text-2xl font-black text-emerald-600 mt-2 font-mono">
            4 <span className="text-xs font-normal text-muted-foreground">/ 5 ô khả dụng (80%)</span>
          </div>
          <div className="text-[11px] text-emerald-700 font-semibold mt-1.5 flex items-center gap-1">
            <CheckCircle2 className="w-3.5 h-3.5" />
            Đủ dự phòng cho kịch bản W3
          </div>
        </Card>

        {/* KPI 3: Pending Approvals */}
        <Card className="p-4 border-border/80 shadow-sm">
          <div className="flex items-center justify-between text-muted-foreground text-xs">
            <span>Hàng đợi chờ duyệt (M12)</span>
            <Clock className="w-4 h-4 text-amber-600" />
          </div>
          <div className="text-2xl font-black text-amber-600 mt-2 font-mono">
            {pendingCount} <span className="text-xs font-normal text-muted-foreground">yêu cầu</span>
          </div>
          <div className="text-[11px] text-amber-800 font-medium mt-1.5">
            Cần xử lý trong 15 phút
          </div>
        </Card>

        {/* KPI 4: Today Revenue Fund */}
        <Card className="p-4 border-border/80 shadow-sm">
          <div className="flex items-center justify-between text-muted-foreground text-xs">
            <span>Quỹ bảo trì BQL tích lũy (20%)</span>
            <Building2 className="w-4 h-4 text-indigo-600" />
          </div>
          <div className="text-2xl font-black text-neutral-900 mt-2 font-mono">
            {formatVnd(1420000)}
          </div>
          <div className="text-[11px] text-neutral-500 mt-1.5">
            Từ 58 lượt chia sẻ hôm nay
          </div>
        </Card>
      </div>

      {/* Main Approval Queue Table / Cards */}
      <Card className="border-border/80 shadow-md">
        <CardHeader className="pb-3 border-b border-neutral-100">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <CardTitle className="text-base font-extrabold flex items-center gap-2">
                <FileText className="w-5 h-5 text-neutral-900" />
                <span>Hàng đợi phê duyệt thỏa thuận & tranh chấp (M12)</span>
              </CardTitle>
              <CardDescription className="text-xs">
                Các giao dịch vượt ngưỡng hoặc kịch bản biên gọi trực tiếp FastAPI `/api/v1/approvals`.
              </CardDescription>
            </div>

            {/* Filter buttons */}
            <div className="flex items-center gap-1 bg-neutral-100 p-1 rounded-xl text-xs">
              <button
                onClick={() => setFilterType("all")}
                className={`px-3 py-1 rounded-lg font-bold transition ${
                  filterType === "all" ? "bg-white text-black shadow-xs" : "text-neutral-500 hover:text-black"
                }`}
              >
                Tất cả ({items.length})
              </button>
              <button
                onClick={() => setFilterType("pending")}
                className={`px-3 py-1 rounded-lg font-bold transition ${
                  filterType === "pending" ? "bg-white text-black shadow-xs" : "text-neutral-500 hover:text-black"
                }`}
              >
                Chờ duyệt ({pendingCount})
              </button>
            </div>
          </div>
        </CardHeader>

        <CardContent className="p-4 space-y-3">
          {isLoading ? (
            <div className="text-center py-10 text-muted-foreground text-xs flex items-center justify-center gap-2">
              <Loader2 className="w-4 h-4 animate-spin text-neutral-900" />
              <span>Đang tải hàng đợi thẩm định từ FastAPI...</span>
            </div>
          ) : filteredItems.length === 0 ? (
            <div className="text-center py-10 text-muted-foreground text-xs">
              Không có yêu cầu nào cần xử lý.
            </div>
          ) : (
            filteredItems.map((item) => (
              <div
                key={item.id}
                className={`p-4 rounded-2xl border transition-all flex flex-col md:flex-row md:items-center justify-between gap-4 ${
                  item.status === "approved"
                    ? "bg-emerald-50/50 border-emerald-200"
                    : item.status === "rejected"
                    ? "bg-neutral-50 border-neutral-200 opacity-60"
                    : "bg-white border-neutral-200/90 shadow-sm hover:border-neutral-300"
                }`}
              >
                {/* Details on Left */}
                <div className="space-y-1.5 flex-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <Badge variant="outline" className="font-mono text-[10px]">
                      {item.code}
                    </Badge>
                    <span className="font-extrabold text-sm text-neutral-900">
                      {item.title}
                    </span>
                    {item.type === "high_value" && (
                      <Badge variant="outline" className="bg-purple-50 text-purple-700 border-purple-200 text-[10px]">
                        Giá trị cao
                      </Badge>
                    )}
                    {item.type === "early_return_swap" && (
                      <Badge variant="warning" className="text-[10px]">
                        Về sớm W3
                      </Badge>
                    )}
                    {item.type === "dimension_exception" && (
                      <Badge variant="outline" className="bg-sky-50 text-sky-700 border-sky-200 text-[10px]">
                        Kích thước xe
                      </Badge>
                    )}
                  </div>

                  <p className="text-xs text-neutral-600 leading-relaxed">
                    {item.reason}
                  </p>

                  <div className="flex items-center gap-4 text-[11px] text-muted-foreground flex-wrap pt-0.5">
                    <span>
                      Người thuê: <strong className="text-neutral-800">{item.renter_name}</strong> ({item.plate_number})
                    </span>
                    <span>
                      Ô đỗ: <strong className="text-neutral-800">{item.slot_code}</strong>
                    </span>
                    <span>
                      Giá trị: <strong className="text-emerald-700 font-mono font-bold">{formatVnd(item.price_vnd)}</strong>
                    </span>
                    <span>{item.created_at_desc}</span>
                  </div>
                </div>

                {/* Actions on Right */}
                <div className="flex items-center gap-2 shrink-0">
                  {item.status === "pending" ? (
                    <>
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={actionInProgress === item.id}
                        onClick={() => handleAction(item.id, "rejected")}
                        className="h-9 px-3 rounded-xl text-xs font-bold text-rose-600 hover:text-rose-700 hover:bg-rose-50 border-rose-200"
                      >
                        <X className="w-3.5 h-3.5 mr-1" />
                        Từ chối
                      </Button>
                      <Button
                        size="sm"
                        variant="uber"
                        disabled={actionInProgress === item.id}
                        onClick={() => handleAction(item.id, "approved")}
                        className="h-9 px-4 rounded-xl text-xs font-bold shadow-sm flex items-center gap-1.5"
                      >
                        {actionInProgress === item.id ? (
                          <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        ) : (
                          <>
                            <Check className="w-3.5 h-3.5 mr-1" />
                            Phê duyệt
                          </>
                        )}
                      </Button>
                    </>
                  ) : item.status === "approved" ? (
                    <Badge className="bg-emerald-600 text-white border-none text-xs flex items-center gap-1 py-1 px-3">
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      ĐÃ PHÊ DUYỆT
                    </Badge>
                  ) : (
                    <Badge variant="outline" className="text-neutral-500 border-neutral-300 text-xs flex items-center gap-1 py-1 px-3">
                      <XCircle className="w-3.5 h-3.5" />
                      ĐÃ TỪ CHỐI
                    </Badge>
                  )}
                </div>
              </div>
            ))
          )}
        </CardContent>
      </Card>
    </div>
  )
}
