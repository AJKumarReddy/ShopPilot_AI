from app.core.errors import CommerceError


class MockPaymentService:
    def __init__(self, mode: str = "approved") -> None:
        self.mode = mode

    async def charge(self, checkout_id: str) -> str:
        if self.mode == "declined":
            raise CommerceError("Mock payment was declined. No order was placed.", 402)
        if self.mode == "processing_error":
            raise CommerceError(
                "Mock payment is temporarily unavailable. No order was placed.", 503
            )
        return f"mock_{checkout_id}"
