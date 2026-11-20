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
        super().__init__(f"User '{user_id}' does not have permission to view agreement '{agreement_id}'.")
