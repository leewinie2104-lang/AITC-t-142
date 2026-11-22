"""Domain exceptions cho module Agreement (M6)."""

from uuid import UUID


class AgreementError(Exception):
    """Base exception cho nghiệp vụ thỏa thuận."""


class AgreementNotFoundError(AgreementError):
    """Không tìm thấy thỏa thuận."""

    def __init__(self, agreement_id: UUID) -> None:
        self.agreement_id = agreement_id
        super().__init__(f"Agreement with id '{agreement_id}' not found.")


class BookingNotFoundError(AgreementError):
    """Không tìm thấy booking để sinh thỏa thuận."""

    def __init__(self, booking_id: UUID) -> None:
        self.booking_id = booking_id
        super().__init__(f"Booking with id '{booking_id}' not found.")


class ZonePolicyNotFoundError(AgreementError):
    """Không tìm thấy chính sách khu vực hiệu lực."""

    def __init__(self, zone_id: UUID) -> None:
        self.zone_id = zone_id
        super().__init__(f"Active zone policy not found for zone '{zone_id}'.")


class AgreementAccessDeniedError(AgreementError):
    """Người dùng không có quyền truy cập thỏa thuận này."""

    def __init__(self, agreement_id: UUID, user_id: UUID) -> None:
        self.agreement_id = agreement_id
        self.user_id = user_id
        super().__init__(f"User '{user_id}' does not have permission to access agreement '{agreement_id}'.")


class InvalidOtpError(AgreementError):
    """Mã OTP không chính xác."""

    def __init__(self, message: str = "Invalid OTP code provided.") -> None:
        super().__init__(message)


class OtpExpiredError(AgreementError):
    """Mã OTP đã hết hạn hoặc chưa được tạo."""

    def __init__(self, message: str = "OTP has expired or was not requested.") -> None:
        super().__init__(message)


class OtpMaxAttemptsExceededError(AgreementError):
    """Đã nhập sai OTP quá số lần quy định."""

    def __init__(self, max_attempts: int = 5) -> None:
        super().__init__(f"Maximum OTP verification attempts ({max_attempts}) exceeded.")


class PartyAlreadyConfirmedError(AgreementError):
    """Bên này đã xác nhận thỏa thuận từ trước."""

    def __init__(self, agreement_id: UUID, role: str) -> None:
        self.agreement_id = agreement_id
        self.role = role
        super().__init__(f"Party '{role}' has already confirmed agreement '{agreement_id}'.")


class AgreementNotPendingError(AgreementError):
    """Thỏa thuận không ở trạng thái chờ xác nhận."""

    def __init__(self, agreement_id: UUID, current_status: str) -> None:
        self.agreement_id = agreement_id
        self.current_status = current_status
        super().__init__(
            f"Agreement '{agreement_id}' is not in 'pending_confirmation' state (current: {current_status})."
        )


class AgreementExpiredError(AgreementError):
    """Đã quá thời hạn xác nhận thỏa thuận."""

    def __init__(self, agreement_id: UUID) -> None:
        self.agreement_id = agreement_id
        super().__init__(f"Agreement '{agreement_id}' confirmation deadline has expired.")
