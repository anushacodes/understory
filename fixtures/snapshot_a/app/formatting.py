def normalize(value: str) -> str:
    """Normalize a display label without changing its case."""
    return " ".join(value.split())


def traced(function):
    """A deliberately inert decorator used by parser fixtures."""
    return function


@traced
async def café_receipt(account_id: str) -> str:
    """Return a Unicode receipt label; does not perform network I/O."""
    def decorate(value: str) -> str:
        return f"café · {value}"
    return decorate(account_id)
