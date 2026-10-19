from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session as DBSession

from backend.dependencies import get_db
from backend.models import Session as SessionModel
from backend.schemas import SessionCreate, SessionResponse

router = APIRouter(tags=["Sessions"])


@router.post("/sessions", response_model=SessionResponse)
def create_session(request: SessionCreate, db: DBSession = Depends(get_db)):
    new_session = SessionModel(title=request.title)

    db.add(new_session)
    db.commit()
    db.refresh(new_session)

    return new_session


@router.get("/sessions", response_model=list[SessionResponse])
def list_sessions(db: DBSession = Depends(get_db)):
    statement = select(SessionModel).order_by(SessionModel.created_at.desc())
    return db.scalars(statement).all()


@router.get("/sessions/{session_id}", response_model=SessionResponse)
def get_session(session_id: UUID, db: DBSession = Depends(get_db)):
    statement = select(SessionModel).where(SessionModel.id == session_id)
    session = db.scalars(statement).first()

    if session is None:
        raise HTTPException(
            status_code=404,
            detail="Session not found",
        )

    return session


@router.delete("/sessions/{session_id}")
def delete_session(session_id: UUID, db: DBSession = Depends(get_db)):
    statement = delete(SessionModel).where(SessionModel.id == session_id)
    result = db.execute(statement)

    if result.rowcount == 0:
        raise HTTPException(
            status_code=404,
            detail="Session not found",
        )

    db.commit()

    return {"message": "Session deleted successfully"}
