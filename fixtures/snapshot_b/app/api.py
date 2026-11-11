"""HTTP-independent request boundary for the synthetic Ledger API."""
from app.validation import validate_payload
from app.service import TransferService


def create_transfer(payload: dict, service: TransferService) -> dict:
    """Validate incoming transfer data before it reaches the service layer."""
    transfer = validate_payload(payload)
    return service.transfer(transfer)


def health() -> dict:
    return {"status": "ok"}
