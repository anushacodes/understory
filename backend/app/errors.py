class AppError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        status: int = 422,
        retryable: bool = False,
        retry_after: float | None = None,
    ):
        self.code = code
        self.message = message
        self.status = status
        self.retryable = retryable
        self.retry_after = retry_after
        super().__init__(message)


class LostLease(Exception):
    pass


class Cancelled(Exception):
    pass


def retry_delay(headers) -> float | None:
    import math
    from datetime import UTC, datetime
    from email.utils import parsedate_to_datetime

    value = headers.get("retry-after")
    if not value:
        return None
    try:
        delay = float(value)
    except ValueError:
        try:
            delay = (parsedate_to_datetime(value) - datetime.now(UTC)).total_seconds()
        except (TypeError, ValueError):
            return None
    return min(300, max(0, delay)) if math.isfinite(delay) else None
