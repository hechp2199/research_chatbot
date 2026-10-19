from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File
from fastapi import UploadFile as FastAPIUploadFile
from fastapi import HTTPException
from pydantic import WithJsonSchema
from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from backend.dependencies import get_db
from backend.models import Paper
from backend.models import Session as SessionModel
from backend.schemas import PaperResponse
from backend.services import paper_service

router = APIRouter(tags=["Papers"])


# Preserve Swagger UI's multiple-file upload support.
BinaryUploadFile = Annotated[
    FastAPIUploadFile,
    WithJsonSchema({"type": "string", "format": "binary"}),
]


@router.get(
    "/sessions/{session_id}/papers",
    response_model=list[PaperResponse],
)
def list_papers(
    session_id: UUID,
    db: DBSession = Depends(get_db),
):
    research_session = db.get(SessionModel, session_id)

    if research_session is None:

        raise HTTPException(
            status_code=404,
            detail="Session not found",
        )

    statement = (
        select(Paper)
        .where(Paper.session_id == session_id)
        .order_by(Paper.created_at.desc())
    )

    return db.scalars(statement).all()


@router.post(
    "/sessions/{session_id}/papers",
    response_model=list[PaperResponse],
    status_code=201,
)
def upload_paper(
    session_id: UUID,
    files: Annotated[
        list[BinaryUploadFile],
        File(description="Select multiple PDF files"),
    ],
    db: DBSession = Depends(get_db),
):
    return paper_service.upload_papers(
        db=db,
        session_id=session_id,
        files=files,
    )
