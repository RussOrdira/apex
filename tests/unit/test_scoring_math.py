from __future__ import annotations

from decimal import Decimal

import pytest

from apex_predict.services.scoring import (
    awarded_points_for_prediction,
    confidence_multiplier_from_credits,
)


@pytest.mark.unit
def test_confidence_multiplier_from_credits() -> None:
    assert confidence_multiplier_from_credits(0) == Decimal("1.00")
    assert confidence_multiplier_from_credits(50) == Decimal("1.50")
    assert confidence_multiplier_from_credits(100) == Decimal("2.00")


@pytest.mark.unit
def test_awarded_points_for_prediction_rounding() -> None:
    assert awarded_points_for_prediction(25, 50) == Decimal("37.50")
    assert awarded_points_for_prediction(10, 33) == Decimal("13.30")


@pytest.mark.unit
def test_scoring_math_rejects_negative_values() -> None:
    with pytest.raises(ValueError, match="credits_must_be_non_negative"):
        confidence_multiplier_from_credits(-1)

    with pytest.raises(ValueError, match="base_points_must_be_non_negative"):
        awarded_points_for_prediction(-5, 50)
