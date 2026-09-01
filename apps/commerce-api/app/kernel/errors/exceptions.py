from app.kernel.errors.codes import TENANT_ACCESS_DENIED


class CruxNexusError(Exception):
    """Base exception for all CruxNexus domain errors."""

    def __init__(self, code: str, message: str, details: dict | None = None):
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(message)


class CapacityExceededError(CruxNexusError):
    """Raised when merchant exceeds their capacity limits."""

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


class AuthorizationError(CruxNexusError):
    def __init__(self, message: str, code: str = TENANT_ACCESS_DENIED):
        super().__init__(code=code, message=message)


# Backward-compatible alias
CapacityExceeded = CapacityExceededError
