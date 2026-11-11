"""In-memory storage for the synthetic fixture; not production persistence."""


class LedgerStore:
    def __init__(self):
        self.entries = []

    def append_transfer(self, payload: dict) -> str:
        self.entries.append(dict(payload))
        return f"receipt-{len(self.entries)}"


def normalize(value: str) -> str:
    """Normalize a storage key."""
    return value.strip().lower()
