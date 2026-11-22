import React from "react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Bot, Send, Sparkles, X, Shield, CornerDownLeft } from "lucide-react"

interface Message {
  id: string
  sender: "user" | "agent"
  text: string
  timestamp: string
}

export const AgentChatDrawer: React.FC = () => {
  const [isOpen, setIsOpen] = React.useState(false)
  const [input, setInput] = React.useState("")
  const [isTyping, setIsTyping] = React.useState(false)
  const [messages, setMessages] = React.useState<Message[]>([
    {
      id: "m-1",
      sender: "agent",
      text: "Xin chào! Tôi là Trợ lý AI ParkSmart (Supervisor Guardrail). Bạn cần tìm ô đỗ gần sảnh nào, hoặc cần tra cứu kích thước xe và quy chế hầm gửi xe?",
      timestamp: "08:30",
    },
  ])

  const messagesEndRef = React.useRef<HTMLDivElement>(null)
  const isMountedRef = React.useRef(true)

  React.useEffect(() => {
    isMountedRef.current = true
    return () => {
      isMountedRef.current = false
    }
  }, [])

  React.useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages, isTyping])

  const handleSend = (userText?: string) => {
    const textToSend = userText || input.trim()
    if (!textToSend) return

    const userMsg: Message = {
      id: `u-${Date.now()}`,
      sender: "user",
      text: textToSend,
      timestamp: new Date().toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit" }),
    }

    setMessages((prev) => [...prev, userMsg])
    setInput("")
    setIsTyping(true)

    // Simulate Agent Thinking & Guardrail Execution (bảo đảm memory leak safety)
    setTimeout(() => {
      if (!isMountedRef.current) return

      let reply = ""
      if (textToSend.includes("sảnh S2") || textToSend.includes("chiều nay")) {
        reply = "✨ Đã phân tích yêu cầu: Tìm chỗ gần Sảnh S2 từ 14:00 - 18:00.\n\n• Ô tối ưu: **B2-045 (TH1 Cư Dân)** cách thang máy S2 chỉ 30m.\n• Đơn giá: 15.000đ/giờ (Tiết kiệm 40% so với bãi ngoài).\n• Trạng thái: Đã có sẵn lịch chia sẻ từ chủ nhà Căn 1408 S2. Bạn có thể bấm chọn ô B2-045 trên sơ đồ để ký thỏa thuận ngay."
      } else if (textToSend.includes("Everest") || textToSend.includes("kích thước")) {
        reply = "📏 Kiểm tra quy tắc kích thước (BR-11):\n\n• Xe Ford Everest có chiều cao 1.837m, chiều dài 4.9m (Xe cỡ L).\n• Chiều cao tĩnh hầm B2 là 2.2m (Đạt an toàn).\n• Khuyến nghị: Chọn hạng **ParkComfort (TH2 - Ô B2-046)** có chiều rộng 2.5m cạnh cột để dễ mở cửa xe mà không va quẹt."
      } else if (textToSend.includes("nội quy") || textToSend.includes("qua đêm")) {
        reply = "📚 Tra cứu quy chế bãi đỗ (RAG PgVector):\n\n• Theo Điều 4.2 Nội quy tòa S2: Xe gửi qua đêm sau 23:00 phải có thỏa thuận điện tử có hiệu lực hoặc đăng ký trước với BQL.\n• Mọi giao dịch chia sẻ chỗ đều được cấp mã thỏa thuận số hóa và bảo đảm quyền đỗ xe tuyệt đối."
      } else {
        reply = `✨ Tôi đã nhận diện yêu cầu: "${textToSend}". Tôi đã kết nối với LangGraph Agent để lọc danh sách ô đỗ phù hợp nhất cho bạn.`
      }

      setMessages((prev) => [
        ...prev,
        {
          id: `a-${Date.now()}`,
          sender: "agent",
          text: reply,
          timestamp: new Date().toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit" }),
        },
      ])
      setIsTyping(false)
    }, 1200)
  }

  return (
    <>
      {/* Floating Action Button */}
      <button
        onClick={() => setIsOpen(true)}
        className="fixed bottom-6 right-6 z-40 flex items-center gap-2 rounded-full bg-neutral-900 px-4 py-3 text-white shadow-2xl border border-neutral-700 hover:scale-105 active:scale-95 transition-all cursor-pointer"
      >
        <span className="relative flex h-2.5 w-2.5">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
          <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500" />
        </span>
        <Sparkles className="w-4 h-4 text-emerald-400" />
        <span className="text-xs font-extrabold tracking-wide">Trợ lý ParkSmart</span>
      </button>

      {/* Slide-in Chat Drawer */}
      {isOpen && (
        <div className="fixed bottom-20 right-4 sm:right-6 z-50 w-[380px] max-w-[calc(100vw-2rem)] rounded-3xl bg-white border border-neutral-200 shadow-2xl flex flex-col overflow-hidden animate-in fade-in slide-in-from-bottom-6 duration-200">
          {/* Header */}
          <div className="bg-neutral-900 p-4 text-white flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-xl bg-emerald-500 text-black flex items-center justify-center font-black text-xs">
                <Bot className="w-5 h-5 text-black" />
              </div>
              <div>
                <div className="flex items-center gap-1.5">
                  <span className="text-xs font-extrabold text-white">ParkSmart AI Copilot</span>
                  <Badge variant="outline" className="text-[9px] font-mono text-emerald-400 border-emerald-500/40 px-1 py-0">
                    Bedrock
                  </Badge>
                </div>
                <div className="flex items-center gap-1 text-[10px] text-neutral-400">
                  <Shield className="w-3 h-3 text-emerald-400" />
                  <span>Privacy Guardrail · PII Masked</span>
                </div>
              </div>
            </div>

            <button
              onClick={() => setIsOpen(false)}
              className="text-neutral-400 hover:text-white p-1 rounded-lg transition-colors cursor-pointer"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Messages Body */}
          <div className="p-4 h-80 overflow-y-auto space-y-3 text-xs bg-neutral-50/50">
            {messages.map((m) => (
              <div
                key={m.id}
                className={`flex flex-col ${m.sender === "user" ? "items-end" : "items-start"}`}
              >
                <div
                  className={`max-w-[85%] rounded-2xl px-3.5 py-2.5 leading-relaxed ${
                    m.sender === "user"
                      ? "bg-neutral-900 text-white rounded-tr-sm"
                      : "bg-white text-neutral-800 border border-neutral-200/80 shadow-sm rounded-tl-sm whitespace-pre-line"
                  }`}
                >
                  {m.text}
                </div>
                <span className="text-[10px] text-neutral-400 mt-1 px-1">{m.timestamp}</span>
              </div>
            ))}

            {isTyping && (
              <div className="flex items-center gap-1.5 text-neutral-400 text-xs italic bg-white p-2.5 rounded-2xl border border-neutral-200/60 w-fit">
                <Sparkles className="w-3.5 h-3.5 text-emerald-500 animate-spin" />
                <span>Agent đang tra cứu quy chế & bản đồ...</span>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Quick Prompts */}
          <div className="p-2.5 bg-white border-t border-neutral-100 flex gap-1.5 overflow-x-auto text-[11px]">
            <button
              onClick={() => handleSend("Tìm chỗ gần sảnh S2 chiều nay")}
              className="shrink-0 bg-neutral-100 hover:bg-neutral-200 text-neutral-700 px-2.5 py-1 rounded-lg transition cursor-pointer"
            >
              📍 Tìm chỗ sảnh S2
            </button>
            <button
              onClick={() => handleSend("Xe Ford Everest có vừa ô đỗ không?")}
              className="shrink-0 bg-neutral-100 hover:bg-neutral-200 text-neutral-700 px-2.5 py-1 rounded-lg transition cursor-pointer"
            >
              📏 Đo xe Everest
            </button>
            <button
              onClick={() => handleSend("Nội quy gửi xe qua đêm khu S2 thế nào?")}
              className="shrink-0 bg-neutral-100 hover:bg-neutral-200 text-neutral-700 px-2.5 py-1 rounded-lg transition cursor-pointer"
            >
              📚 Nội quy gửi đêm
            </button>
          </div>

          {/* Input Footer */}
          <div className="p-3 bg-white border-t border-neutral-100 flex items-center gap-2">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSend()}
              placeholder="Nhập yêu cầu bằng tiếng Việt..."
              className="flex-1 bg-neutral-100 rounded-xl px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-neutral-900"
            />
            <Button
              size="icon"
              variant="uber"
              onClick={() => handleSend()}
              className="w-8 h-8 rounded-xl shrink-0 cursor-pointer"
            >
              {input ? <Send className="w-3.5 h-3.5" /> : <CornerDownLeft className="w-3.5 h-3.5" />}
            </Button>
          </div>
        </div>
      )}
    </>
  )
}
