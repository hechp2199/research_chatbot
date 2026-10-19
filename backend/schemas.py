from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SessionResponse(BaseModel):
    id: UUID
    title: str
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SessionCreate(BaseModel):
    title: str = Field(
        default="Research Session",
        min_length=1,
        max_length=200,
    )


class PaperResponse(BaseModel):
    id: UUID
    session_id: UUID
    filename: str
    status: str
    error_message: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
