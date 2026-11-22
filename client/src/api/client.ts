import axios, { type AxiosInstance } from "axios"
import { useAuthStore } from "@/store/useAuthStore"

const API_BASE_URL = import.meta.env.VITE_API_URL || "/api/v1"

export const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
  timeout: 10000,
})

// Request Interceptor: Gắn tự động Identity Headers (X-User-Id, X-Zone-Id) từ Auth Store
apiClient.interceptors.request.use(
  (config) => {
    const { currentUser } = useAuthStore.getState()
    if (currentUser) {
      config.headers["X-User-Id"] = currentUser.id
      config.headers["X-Zone-Id"] = currentUser.zoneId
    }
    return config
  },
  (error) => Promise.reject(error)
)

// Response Interceptor: Chuẩn hóa error message
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const detail = error.response?.data?.detail || error.message || "Đã xảy ra lỗi không xác định"
    return Promise.reject(new Error(detail))
  }
)
