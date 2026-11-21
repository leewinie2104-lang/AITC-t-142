"""Plate normalization and masking: the canonical form that gets hashed (seed, M2 vehicles, N1 LPR matching)."""

import pytest

from app.facility.domain.plate import InvalidPlateError, mask, normalize


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        pytest.param("30A12345", "30A12345", id="already-normalized"),
        pytest.param("30A-123.45", "30A12345", id="dash-and-dot"),
        pytest.param("30a 123 45", "30A12345", id="lowercase-and-spaces"),
        pytest.param("  29C-999.99\n", "29C99999", id="surrounding-whitespace"),
        pytest.param("59X1-123.45", "59X112345", id="motorbike-nine-chars"),
        pytest.param("51G-333.33", "51G33333", id="hcm-province"),
        pytest.param("30A-123.45!", "30A12345", id="stray-symbol-is-separator-noise"),
    ],
)
def test_normalize_accepts_formatting_variants(raw: str, expected: str) -> None:
    assert normalize(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        pytest.param("", id="empty"),
        pytest.param("---", id="only-separators"),
        pytest.param("ABC12345", id="no-province-digits"),
        pytest.param("30A1", id="too-short"),
        pytest.param("30A123456789", id="too-long"),
    ],
)
def test_normalize_rejects_non_plates(raw: str) -> None:
    with pytest.raises(InvalidPlateError):
        normalize(raw)


def test_error_message_never_contains_the_plate() -> None:
    with pytest.raises(InvalidPlateError) as exc:
        normalize("ZZ-secret")
    assert "secret" not in str(exc.value).lower()
    assert "zz" not in str(exc.value).lower()


@pytest.mark.parametrize(
    ("plate", "expected"),
    [
        pytest.param("30A12345", "30A-•••.45", id="normalized-input"),
        pytest.param("30A-123.45", "30A-•••.45", id="raw-input"),
        pytest.param("29C99999", "29C-•••.99", id="other-province"),
        pytest.param("59X112345", "59X-•••.45", id="nine-chars"),
    ],
)
def test_mask_hides_the_middle(plate: str, expected: str) -> None:
    assert mask(plate) == expected


def test_mask_never_reveals_the_full_plate() -> None:
    plate = "30A12345"
    masked = mask(plate)
    assert plate not in masked
    assert "123" not in masked
