"""Static example for locating service-level test source."""
from app.service import TransferService
from app.storage import LedgerStore


def test_receipt_is_returned():
    result = TransferService(LedgerStore()).transfer({"account_id": "a", "amount": 10})
    assert result == {"receipt_id": "receipt-1", "accepted": True}
