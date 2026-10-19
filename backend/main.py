from uuid import UUID, uuid4
from fastapi import FastAPI, Depends, HTTPException, File
from fastapi import UploadFile as FastAPIUploadFile
from sqlalchemy import text, select, delete, func
from sqlalchemy.orm import Session as DBSession
from backend.database import engine
from pathlib import Path
from typing import Annotated
from pydantic import WithJsonSchema
import hashlib

from backend.database import SessionLocal
from backend.models import Session as SessionModel
from backend.models import Paper
from backend.schemas import SessionCreate, SessionResponse, PaperResponse

app = FastAPI(title="Research Paper Chatbot")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/health")
def health_check():
    return {"status": "healthy"}


@app.get("/health/db")
def database_health():
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return {"database": "connected"}


@app.post("/sessions", response_model=SessionResponse)
def create_session(request: SessionCreate, db: DBSession = Depends(get_db)):
    new_session = SessionModel(title=request.title)
    db.add(new_session)
    db.commit()
    db.refresh(new_session)
    return new_session


@app.get("/sessions", response_model=list[SessionResponse])
def list_sessions(db: DBSession = Depends(get_db)):
    statement = select(SessionModel).order_by(SessionModel.created_at.desc())
    sessions = db.scalars(statement).all()
    return sessions


@app.get("/sessions/{session_id}", response_model=SessionResponse)
def get_session(
    session_id: UUID,
    db: DBSession = Depends(get_db),
):
    statement = select(SessionModel).where(SessionModel.id == session_id)
    session = db.scalars(statement).first()

    if session is None:
        raise HTTPException(
            status_code=404,
            detail="Session not found",
        )

    return session


@app.delete("/sessions/{session_id}")
def delete_session(
    session_id: UUID,
    db: DBSession = Depends(get_db),
):
    statement = delete(SessionModel).where(SessionModel.id == session_id)
    result = db.execute(statement)

    if result.rowcount == 0:
        raise HTTPException(
            status_code=404,
            detail="Session not found",
        )

    db.commit()
    return {"message": "Session deleted successfully"}


@app.get("/sessions/{session_id}/papers", response_model=list[PaperResponse])
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


MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
PDF_STORAGE_DIR = Path("data/pdfs")
BinaryUploadFile = Annotated[
    FastAPIUploadFile, WithJsonSchema({"type": "string", "format": "binary"})
] # Added this to overcome the multi-file upload issue with swagger UI


@app.post(
    "/sessions/{session_id}/papers", response_model=list[PaperResponse], status_code=201
)
def upload_paper(
    session_id: UUID,
    files: Annotated[
        list[BinaryUploadFile], File(description="Select multiple PDF files")
    ],
    db: DBSession = Depends(get_db),
):
    try:
        research_session = db.get(SessionModel, session_id)

        if research_session is None:
            raise HTTPException(
                status_code=404,
                detail="Session not found",
            )

        if not files:
            raise HTTPException(
                status_code=400,
                detail="Upload at least one PDF",
            )

        # Check the session's total PDF limit before processing files.
        paper_count = db.scalar(
            select(func.count())
            .select_from(Paper)
            .where(Paper.session_id == session_id)
        )
        if paper_count + len(files) > 10:
            raise HTTPException(
                status_code=400,
                detail="A session can contain a maximum of 10 PDFs.",
            )

        # Get hashes of PDFs already uploaded to this session.
        existing_hashes = set(
            db.scalars(
                select(Paper.file_hash).where(
                    Paper.session_id == session_id,
                    Paper.file_hash.is_not(None),
                )
            ).all()
        )

        batch_hashes = set()
        validated_files = []

        # Phase 1: Validate every file before saving anything.
        for file in files:
            if not file.filename or Path(file.filename).suffix.lower() != ".pdf":
                raise HTTPException(
                    status_code=400,
                    detail="Only PDF files are allowed",
                )

            content = file.file.read(MAX_FILE_SIZE + 1)

            if len(content) > MAX_FILE_SIZE:
                raise HTTPException(
                    status_code=413,
                    detail=f"{file.filename} exceeds the 10 MB limit",
                )

            if not content.startswith(b"%PDF-"):
                raise HTTPException(
                    status_code=400,
                    detail=f"{file.filename} is not a valid PDF",
                )

            file_hash = hashlib.sha256(content).hexdigest()

            if file_hash in existing_hashes or file_hash in batch_hashes:
                raise HTTPException(
                    status_code=409,
                    detail=(f"Duplicate PDF detected: {file.filename}"),
                )

            batch_hashes.add(file_hash)

            validated_files.append(
                {
                    "filename": Path(file.filename).name,
                    "content": content,
                    "file_hash": file_hash,
                }
            )

        # Phase 2: Save files and create database records.
        PDF_STORAGE_DIR.mkdir(parents=True, exist_ok=True)

        saved_paths = []
        papers = []

        try:
            for item in validated_files:
                stored_path = PDF_STORAGE_DIR / f"{uuid4()}.pdf"
                stored_path.write_bytes(item["content"])
                saved_paths.append(stored_path)

                paper = Paper(
                    session_id=session_id,
                    filename=item["filename"],
                    file_hash=item["file_hash"],
                    status="PENDING",
                )

                db.add(paper)
                papers.append(paper)

            db.commit()

            for paper in papers:
                db.refresh(paper)

            return papers

        except Exception:
            db.rollback()

            for path in saved_paths:
                path.unlink(missing_ok=True)

            raise

    finally:
        for file in files:
            file.file.close()
