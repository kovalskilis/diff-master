from fastapi import status as http_status


class BaseAppException(Exception):
    def __init__(self, message: str, reason: str, status: int):
        self.message = message
        self.reason = reason
        self.status = status
        super().__init__(message)


