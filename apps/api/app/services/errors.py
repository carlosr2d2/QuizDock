class DomainError(Exception):
    status_code = 400

    def __init__(self, message: str, status_code: int | None = None) -> None:
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        super().__init__(message)


class NotFoundError(DomainError):
    status_code = 404


class ForbiddenError(DomainError):
    status_code = 403


class ConflictError(DomainError):
    status_code = 409


class InsufficientCreditsError(DomainError):
    status_code = 402

    def __init__(self, required: int, available: int) -> None:
        self.required = required
        self.available = available
        super().__init__(f"Créditos insuficientes: se necesitan {required}, hay {available}", 402)
