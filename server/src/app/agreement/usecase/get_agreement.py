"""Use case: Xem chi tiết thỏa thuận (M6, SCRUM-99, GET /agreements/{id}).

Xử lý:
- Truy vấn thỏa thuận theo ID.
- Kiểm tra phân quyền truy cập (RLS / Auth Guard):
  + Cư dân là bên cho thuê (provider) hoặc bên thuê (renter).
  + Nhân viên BQL/Bảo vệ thuộc khu vực chứa thỏa thuận.
  + System admin / worker.
"""

import logging
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from app.agreement.domain.exceptions import (
    AgreementAccessDeniedError,
    AgreementNotFoundError,
)
from app.agreement.domain.models import AgreementRecord
from app.agreement.domain.ports import AgreementRepositoryPort

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GetAgreementQuery:
    """Tham số truy vấn thỏa thuận."""

    agreement_id: UUID
    requester_user_id: UUID
    requester_role: str
    requester_zone_ids: list[UUID]


class GetAgreementUseCase:
    """Truy xuất thỏa thuận kèm xác thực quyền truy cập."""

    def __init__(self, repo: AgreementRepositoryPort) -> None:
        self.repo = repo

    async def execute(self, conn: Any, query: GetAgreementQuery) -> AgreementRecord:
        agreement = await self.repo.get_by_id(conn, query.agreement_id)
        if agreement is None:
            raise AgreementNotFoundError(query.agreement_id)

        # Kiểm tra quyền:
        # 1. Staff của khu vực chứa ô đỗ (zone_manager, guard, system, chain_operator)
        is_staff = (
            query.requester_role in {"zone_manager", "guard", "system", "chain_operator"}
            and agreement.zone_id in query.requester_zone_ids
        )
        # 2. Bên tham gia thỏa thuận (provider hoặc renter)
        is_party = query.requester_user_id in {
            agreement.provider_user_id,
            agreement.renter_user_id,
        }

        if not (is_staff or is_party):
            logger.warning(
                "Access denied: user %s (role=%s) tried to access agreement %s in zone %s",
                query.requester_user_id,
                query.requester_role,
                query.agreement_id,
                agreement.zone_id,
            )
            raise AgreementAccessDeniedError(query.agreement_id, query.requester_user_id)

        return agreement
