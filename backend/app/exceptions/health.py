from fastapi import status as http_status
from .base import BaseAppException


class HealthNotFoundError(BaseAppException):
    def __init__(
        self,
        message: str = "Health not found.",
        reason: str = "health_not_found_error",
        status: int = http_status.HTTP_404_NOT_FOUND,
    ):
        super().__init__(message=message, reason=reason, status=status)


