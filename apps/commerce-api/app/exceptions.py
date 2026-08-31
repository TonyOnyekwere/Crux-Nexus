class CruxNexusError(Exception):
    code: str

    def __init__(self, code: str, message: str, details: dict | None = None):
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(message)


class CapacityExceeded(CruxNexusError):
    def __init__(self, resource: str, capacity: int, current: int):
        super().__init__(
            code=f"{resource.upper()}_CAPACITY_EXCEEDED",
            message=f"This merchant has reached its {resource} capacity.",
            details={"capacity": capacity, "current": current},
        )


class NotFoundError(CruxNexusError):
    def __init__(self, resource: str, message: str | None = None):
        super().__init__(
            code=f"{resource.upper()}_NOT_FOUND",
            message=message or f"{resource} not found.",
        )
