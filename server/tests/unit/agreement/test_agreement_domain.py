"""Unit tests for Agreement domain logic (M6, SCRUM-99)."""

import hashlib
from datetime import UTC, datetime
from uuid import uuid4

from app.agreement.domain.models import AgreementRecord, AgreementStatus
from app.agreement.domain.rendering import (
    check_requires_approval,
    compute_body_hash,
    render_agreement_template,
)


def test_render_agreement_template_standard_placeholders() -> None:
    template = (
        "# Thỏa thuận chia sẻ chỗ đỗ\n"
        "Bên cho thuê {{provider}} chia sẻ chỗ {{slot}} cho Bên thuê {{renter}} "
        "trong khoảng {{period}}, giá {{price_vnd}} đ."
    )
    context = {
        "provider": "Nguyễn Thị Lan",
        "renter": "Trần Văn Bình",
        "slot": "B2-045",
        "period": "08:00 20/11/2026 - 12:00 20/11/2026",
        "price_vnd": "40.000",
    }

    result = render_agreement_template(template, context)

    assert "Nguyễn Thị Lan" in result
    assert "Trần Văn Bình" in result
    assert "B2-045" in result
    assert "40.000 đ" in result
    assert "{{" not in result


def test_render_agreement_template_with_spacing_and_unknown_keys() -> None:
    template = "Chào {{ name }}, chỗ của bạn là {{   slot_code }} mã {{ unknown_tag }}."
    context = {
        "name": "Bình",
        "slot_code": "A-101",
    }

    result = render_agreement_template(template, context)

    assert result == "Chào Bình, chỗ của bạn là A-101 mã {{ unknown_tag }}."


def test_render_agreement_template_datetime_formatting() -> None:
    template = "Bắt đầu từ: {{ start_time }}"
    context = {
        "start_time": datetime(2026, 11, 20, 8, 30),
    }

    result = render_agreement_template(template, context)

    assert result == "Bắt đầu từ: 08:30 20/11/2026"


def test_render_agreement_template_datetime_formatting_utc_to_vn() -> None:
    # 01:30 UTC chuyển thành 08:30 UTC+7 (giờ Việt Nam)
    template = "Bắt đầu từ: {{ start_time }}"
    context = {
        "start_time": datetime(2026, 11, 20, 1, 30, tzinfo=UTC),
    }

    result = render_agreement_template(template, context)

    assert result == "Bắt đầu từ: 08:30 20/11/2026"


def test_compute_body_hash_32_bytes_sha256() -> None:
    text = "Thỏa thuận mẫu kiểm thử chữ ký điện tử"
    digest = compute_body_hash(text)

    # Invariant: length must be 32 bytes
    assert len(digest) == 32
    assert isinstance(digest, bytes)
    # Expected SHA-256
    expected = hashlib.sha256(text.encode("utf-8")).digest()
    assert digest == expected


def test_check_requires_approval_threshold() -> None:
    # Mặc định ngưỡng 1.000.000đ (BR-12 / D-08)
    assert not check_requires_approval(40_000, 1_000_000)
    assert not check_requires_approval(999_999, 1_000_000)
    assert check_requires_approval(1_000_000, 1_000_000)
    assert check_requires_approval(1_470_000, 1_000_000)


def test_agreement_record_body_sha256_hex() -> None:
    text = "Nội dung thỏa thuận"
    sha = compute_body_hash(text)
    record = AgreementRecord(
        id=uuid4(),
        zone_id=uuid4(),
        booking_id=uuid4(),
        zone_policy_id=uuid4(),
        provider_user_id=uuid4(),
        renter_user_id=uuid4(),
        price_vnd=40_000,
        body_rendered=text,
        body_sha256=sha,
        status=AgreementStatus.pending_confirmation,
        requires_approval=False,
        confirm_deadline=datetime.now(UTC),
    )

    assert record.body_sha256_hex == sha.hex()
