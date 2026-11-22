"""Router cho BQL Tòa nhà thẩm định và phê duyệt yêu cầu (M12, ADR-0010)."""

from datetime import datetime, timezone
from typing import Literal
from uuid import UUID
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from demo_seed.ids import demo_id


class ApprovalItemOut(BaseModel):
    id: UUID
    code: str
    type: Literal["high_value", "early_return_swap", "overstay_dispute", "dimension_exception"]
    title: str
    agreement_id: str
    slot_code: str
    renter_name: str
    plate_number: str
    price_vnd: int
    reason: str
    created_at_desc: str
    status: Literal["pending", "approved", "rejected"]


class DecideApprovalIn(BaseModel):
    decision: Literal["approved", "rejected"]
    note: str | None = Field(default=None, description="Ghi chú thẩm định của BQL")


class DecideApprovalOut(BaseModel):
    id: UUID
    status: str
    decided_at: datetime
    message: str


# In-Memory Queue mẫu chuẩn BQL
_APPROVAL_QUEUE: list[ApprovalItemOut] = [
    ApprovalItemOut(
        id=demo_id("approval", "01"),
        code="APPR-202611-0089",
        type="high_value",
        title="Thuê nhiều ngày liên tiếp (> 500.000đ)",
        agreement_id="AGR-202611-0089",
        slot_code="B2-012",
        renter_name="Đỗ Minh Tuấn",
        plate_number="30G-999.12",
        price_vnd=750000,
        reason="Hợp đồng thuê 5 ngày công tác vượt ngưỡng phê duyệt tự động của hệ thống.",
        created_at_desc="10 phút trước",
        status="pending",
    ),
    ApprovalItemOut(
        id=demo_id("approval", "02"),
        code="APPR-202611-0090",
        type="dimension_exception",
        title="Xe quá khổ xin cấp phép vào Hầm B2",
        agreement_id="AGR-202611-0090",
        slot_code="B2-046 (TH2)",
        renter_name="Nguyễn Hoàng Nam",
        plate_number="29H-778.99",
        price_vnd=180000,
        reason="Xe Ford F-150 chiều cao 1.95m (hạn mức hầm 2.0m). Đã kiểm tra mô phỏng 3D đạt an toàn.",
        created_at_desc="25 phút trước",
        status="pending",
    ),
    ApprovalItemOut(
        id=demo_id("approval", "03"),
        code="APPR-202611-0091",
        type="early_return_swap",
        title="Chủ chỗ căn 1408 về sớm - Đổi ô TH3-01",
        agreement_id="AGR-202611-0045",
        slot_code="TH3-01",
        renter_name="Trần Anh Quân",
        plate_number="30A-888.88",
        price_vnd=135000,
        reason="Tự động kích hoạt cơ chế W3: Di chuyển khách sang ô TH3 dự phòng của BQL.",
        created_at_desc="3 phút trước",
        status="pending",
    ),
]

router = APIRouter(prefix="/api/v1/approvals", tags=["approvals"])


@router.get("", response_model=list[ApprovalItemOut])
async def list_approvals() -> list[ApprovalItemOut]:
    """Lấy toàn bộ hàng đợi thẩm định của BQL."""
    return _APPROVAL_QUEUE


@router.post("/{id}/decide", response_model=DecideApprovalOut)
async def decide_approval(id: UUID, payload: DecideApprovalIn) -> DecideApprovalOut:
    """Ký phê duyệt hoặc từ chối yêu cầu trong hàng đợi."""
    target = next((item for item in _APPROVAL_QUEUE if item.id == id), None)
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approval request not found.")

    target.status = payload.decision
    now = datetime.now(timezone.utc)

    return DecideApprovalOut(
        id=target.id,
        status=target.status,
        decided_at=now,
        message=f"Đã {'phê duyệt' if payload.decision == 'approved' else 'từ chối'} thành công yêu cầu {target.code}.",
    )
