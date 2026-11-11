from app.storage import LedgerStore


class TransferService:
    """Coordinates a transfer without owning HTTP or database details."""

    def __init__(self, store: LedgerStore):
        self.store = store

    def transfer(self, payload: dict) -> dict:
        """Persist an accepted transfer and return its receipt."""
        receipt = self.store.append_transfer(payload)
        return {"receipt_id": receipt, "accepted": True}
