"""Validation contracts for incoming transfer requests."""


class ValidationError(ValueError):
    """The request does not satisfy the transfer contract."""


def validate_payload(payload: dict) -> dict:
    """Require account_id and an integer amount between 1 and 1,000,000 cents."""
    account_id = payload.get("account_id")
    amount = payload.get("amount")
    if not isinstance(account_id, str) or not account_id.strip():
        raise ValidationError("account_id must be a nonempty string")
    if not isinstance(amount, int) or isinstance(amount, bool) or amount <= 0 or amount > 1_000_000:
        raise ValidationError("amount must be between 1 and 1,000,000 cents")
    return {"account_id": account_id.strip(), "amount": amount}
