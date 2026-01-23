from fastapi import HTTPException, status
from typing import Optional
from datetime import datetime


class NotFoundError(HTTPException):
    def __init__(self, detail: str = "Not Found"):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


class ConflictError(HTTPException):
    def __init__(self, detail: str = "Conflict"):
        super().__init__(status_code=status.HTTP_409_CONFLICT, detail=detail)


class AssignmentConflictError(Exception):
    """Raised when an item is already assigned to another user."""

    def __init__(self, message: str, assigned_to: str, assigned_at: Optional[datetime] = None):
        super().__init__(message)
        self.assigned_to = assigned_to
        self.assigned_at = assigned_at
