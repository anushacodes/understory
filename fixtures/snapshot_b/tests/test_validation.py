"""Static example tests; the importer never executes this file."""
from app.validation import ValidationError, validate_payload


def test_positive_amount():
    assert validate_payload({"account_id": "a", "amount": 10})["amount"] == 10


def test_zero_amount_rejected():
    try:
        validate_payload({"account_id": "a", "amount": 0})
    except ValidationError:
        return
    raise AssertionError("expected validation failure")


def test_oversize_amount_rejected():
    try:
        validate_payload({"account_id": "a", "amount": 1_000_001})
    except ValidationError:
        return
    raise AssertionError("expected upper-bound validation failure")
