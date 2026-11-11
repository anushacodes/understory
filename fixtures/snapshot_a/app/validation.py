"""Validation contracts for incoming transfer requests."""


class ValidationError(ValueError):
    """The request does not satisfy the transfer contract."""


def validate_payload(payload: dict) -> dict:
    """Require account_id and a positive integer amount in cents."""
    account_id = payload.get("account_id")
    amount = payload.get("amount")
    if not isinstance(account_id, str) or not account_id.strip():
        raise ValidationError("account_id must be a nonempty string")
    if not isinstance(amount, int) or isinstance(amount, bool) or amount <= 0:
        raise ValidationError("amount must be a positive integer")
    return {"account_id": account_id.strip(), "amount": amount}
