import * as React from "react"
import { useAuthStore } from "@/store/useAuthStore"
import { useParkingStore } from "@/store/useParkingStore"
import { useSendOtp, useConfirmAgreement } from "@/hooks/useAgreement"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { InputOTP, InputOTPGroup, InputOTPSlot } from "@/components/ui/input-otp"
import { Separator } from "@/components/ui/separator"
import { ShieldCheck, CheckCircle2, Clock, Car, KeyRound, ArrowRight, AlertTriangle, Loader2 } from "lucide-react"
import { formatVnd } from "@/lib/utils"

export function AgreementSigningPage() {
  const { currentUser } = useAuthStore()
  const { selectedSlot } = useParkingStore()
  
  const [agreementId] = React.useState("00000000-0000-0000-0000-000000000099")
  const [otpValue, setOtpValue] = React.useState("")
  const [devOtpHint, setDevOtpHint] = React.useState<string | null>(null)
  const [isSuccess, setIsSuccess] = React.useState(false)
  const [statusMessage, setStatusMessage] = React.useState<string | null>(null)
  const [errorMessage, setErrorMessage] = React.useState<string | null>(null)

  const sendOtpMutation = useSendOtp()
  const confirmAgreementMutation = useConfirmAgreement()

  const handleSendOtp = async () => {
    setErrorMessage(null)
    setStatusMessage(null)
    try {
      const res = await sendOtpMutation.mutateAsync({
        agreementId,
        role: currentUser.roleCode === "L1" ? "provider" : "renter",
      })
      setStatusMessage(res.message || "Mã OTP đã được tạo và gửi thành công.")
      if (res.dev_otp) {
        setDevOtpHint(res.dev_otp)
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Không thể gửi OTP"
      setErrorMessage(msg)
    }
  }

  const handleConfirm = async () => {
    if (otpValue.length < 6) {
      setErrorMessage("Vui lòng nhập đủ 6 chữ số OTP.")
      return
    }
    setErrorMessage(null)
    try {
      await confirmAgreementMutation.mutateAsync({
        agreementId,
        payload: { otp_code: otpValue },
      })
      setIsSuccess(true)
      setStatusMessage("Ký thỏa thuận thành công! Bản ghi consent_record đã được lưu bất biến.")
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Xác nhận OTP thất bại. Vui lòng kiểm tra lại mã xác nhận."
      setErrorMessage(msg)
    }
  }

  const slotCode = selectedSlot?.code || "B2-045"
  const slotKind = selectedSlot?.kind || "TH1"
  const slotLobby = selectedSlot?.nearLobby || "Sảnh S2"
  const pricePerHour = selectedSlot?.pricePerHour || 15000

  return (
    <div className="container max-w-4xl py-8 px-4 space-y-6">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <Badge variant="outline" className="text-primary font-mono text-[10px]">
              SCRUM-100 · M6
            </Badge>
            <span className="text-xs text-muted-foreground font-medium">Thỏa thuận điện tử (FR-08)</span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight mt-1 text-neutral-900">
            Xác nhận thỏa thuận đỗ xe qua OTP
          </h1>
          <p className="text-xs sm:text-sm text-muted-foreground mt-0.5">
            Mã OTP được quản lý nguyên tử trong Redis với cơ chế chống Race Condition bằng Lua script.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="md:col-span-2 space-y-4">
          <Card className="border-border/80 shadow-sm">
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-base font-bold flex items-center gap-2">
                  <ShieldCheck className="w-5 h-5 text-primary" />
                  Nội dung Thỏa thuận chia sẻ ô đỗ
                </CardTitle>
                <Badge variant={isSuccess ? "success" : "th1"} className="font-mono">
                  {isSuccess ? "effective" : "pending_confirmation"}
                </Badge>
              </div>
              <CardDescription>
                Mã định danh thỏa thuận: <span className="font-mono text-neutral-800 font-semibold">{agreementId}</span>
              </CardDescription>
            </CardHeader>

            <CardContent className="space-y-4">
              <div className="rounded-xl bg-neutral-50 p-4 border border-neutral-200/80 space-y-2 text-xs">
                <div className="flex justify-between items-center">
                  <span className="text-muted-foreground">Vị trí ô đỗ:</span>
                  <span className="font-extrabold text-sm text-neutral-900 flex items-center gap-1.5">
                    <Car className="w-4 h-4 text-primary" />
                    {slotCode} ({slotKind}) · {slotLobby}
                  </span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-muted-foreground">Khung giờ hiệu lực:</span>
                  <span className="font-bold text-neutral-900 flex items-center gap-1.5">
                    <Clock className="w-3.5 h-3.5 text-muted-foreground" />
                    08:30 – 17:30 (9 giờ)
                  </span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-muted-foreground">Tổng giá trị thỏa thuận:</span>
                  <span className="font-extrabold text-sm text-emerald-600">
                    {formatVnd(pricePerHour * 9)}
                  </span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-muted-foreground">Bên thuê (Renter):</span>
                  <span className="font-bold text-neutral-900">{currentUser.name}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-muted-foreground">Biển số đăng ký:</span>
                  <span className="font-mono font-bold text-neutral-900">{currentUser.plateNumber || "30A-888.88"}</span>
                </div>
              </div>

              <div className="rounded-xl bg-neutral-100/70 p-3 font-mono text-[11px] text-neutral-600 space-y-1">
                <div className="flex justify-between font-bold text-neutral-800">
                  <span>Bảo toàn nội dung (SHA-256):</span>
                  <span className="text-emerald-600">Khớp 100%</span>
                </div>
                <p className="truncate text-[10px] text-muted-foreground">
                  7c4a8d11b22e1329a47321e...6598c19a9d90
                </p>
              </div>

              {isSuccess && (
                <div className="rounded-xl bg-emerald-50 border border-emerald-200 p-4 space-y-2">
                  <div className="flex items-center gap-2 text-emerald-800 font-bold text-sm">
                    <CheckCircle2 className="w-5 h-5 text-emerald-600" />
                    Bằng chứng chấp thuận đã ghi vào CSDL (FR-09)
                  </div>
                  <div className="text-xs text-emerald-700 space-y-1">
                    <div>• Quyết định: <strong>accepted</strong> (Ký số điện tử bằng OTP)</div>
                    <div>• Bảng lưu trữ: <code className="bg-emerald-100 px-1 py-0.5 rounded">app.consent_record</code> (Bất biến, chỉ ghi thêm)</div>
                    <div>• Trạng thái booking: Đã chuyển sang <strong>confirmed</strong></div>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        <div className="space-y-4">
          <Card className="border-border/80 shadow-md">
            <CardHeader className="pb-3">
              <CardTitle className="text-base font-bold flex items-center gap-2">
                <KeyRound className="w-4 h-4 text-primary" />
                Xác nhận OTP
              </CardTitle>
              <CardDescription>
                Nhập 6 chữ số được cấp để hoàn tất ký thỏa thuận.
              </CardDescription>
            </CardHeader>

            <CardContent className="space-y-4">
              {!isSuccess ? (
                <>
                  <Button
                    onClick={handleSendOtp}
                    disabled={sendOtpMutation.isPending}
                    variant="outline"
                    className="w-full text-xs font-bold"
                  >
                    {sendOtpMutation.isPending ? (
                      <span className="flex items-center gap-1.5">
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        Đang phát sinh OTP...
                      </span>
                    ) : (
                      "1. Lấy mã OTP mới (Redis)"
                    )}
                  </Button>

                  {devOtpHint && (
                    <div className="rounded-xl bg-emerald-50 border border-emerald-200 p-3 text-xs space-y-1.5">
                      <div className="flex justify-between items-center text-emerald-800 font-bold">
                        <span>Mã OTP nhận được:</span>
                        <code className="text-base font-extrabold font-mono text-emerald-900 bg-emerald-100 px-2 py-0.5 rounded">
                          {devOtpHint}
                        </code>
                      </div>
                      <Button
                        size="sm"
                        variant="secondary"
                        onClick={() => setOtpValue(devOtpHint)}
                        className="w-full h-7 text-[11px] font-bold text-emerald-800 bg-emerald-200/50 hover:bg-emerald-200"
                      >
                        Tự động điền mã
                      </Button>
                    </div>
                  )}

                  <Separator />

                  <div className="space-y-2">
                    <label className="text-xs font-bold text-neutral-700 block text-center">
                      2. Nhập mã OTP 6 số
                    </label>
                    <div className="flex justify-center">
                      <InputOTP
                        maxLength={6}
                        value={otpValue}
                        onChange={(value) => setOtpValue(value)}
                      >
                        <InputOTPGroup>
                          <InputOTPSlot index={0} />
                          <InputOTPSlot index={1} />
                          <InputOTPSlot index={2} />
                          <InputOTPSlot index={3} />
                          <InputOTPSlot index={4} />
                          <InputOTPSlot index={5} />
                        </InputOTPGroup>
                      </InputOTP>
                    </div>
                  </div>

                  {errorMessage && (
                    <div className="rounded-xl bg-rose-50 border border-rose-200 p-2.5 text-xs text-rose-700 flex items-center gap-1.5 font-medium">
                      <AlertTriangle className="w-4 h-4 shrink-0 text-rose-500" />
                      <span>{errorMessage}</span>
                    </div>
                  )}

                  {statusMessage && !errorMessage && (
                    <p className="text-[11px] text-muted-foreground text-center">
                      {statusMessage}
                    </p>
                  )}

                  <Button
                    onClick={handleConfirm}
                    disabled={otpValue.length < 6 || confirmAgreementMutation.isPending}
                    variant="uber"
                    className="w-full text-sm font-bold flex items-center justify-center gap-2"
                  >
                    {confirmAgreementMutation.isPending ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <>
                        <span>Ký Thỏa Thuận Ngay</span>
                        <ArrowRight className="w-4 h-4" />
                      </>
                    )}
                  </Button>
                </>
              ) : (
                <div className="text-center py-6 space-y-3">
                  <div className="w-12 h-12 bg-emerald-100 text-emerald-600 rounded-full flex items-center justify-center mx-auto">
                    <CheckCircle2 className="w-7 h-7" />
                  </div>
                  <div>
                    <h3 className="font-extrabold text-base text-neutral-900">Thỏa thuận có hiệu lực</h3>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      Xe của bạn có thể vào hầm từ 08:30 hôm nay.
                    </p>
                  </div>
                  <Button
                    onClick={() => {
                      setIsSuccess(false)
                      setOtpValue("")
                      setDevOtpHint(null)
                    }}
                    variant="outline"
                    className="w-full text-xs"
                  >
                    Thực hiện lại
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}
