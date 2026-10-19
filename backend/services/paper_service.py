import hashlib
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session as DBSession

from backend.models import Paper
from backend.models import Session as SessionModel

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
PDF_STORAGE_DIR = Path("data/pdfs")


def upload_papers(
    db: DBSession,
    session_id: UUID,
    files,
) -> list[Paper]:
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

        # Enforce the session's PDF limit.
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

        # Hashes of PDFs already uploaded to this session.
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

        # Phase 1: Validate the entire batch before writing files.
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
                    detail=f"Duplicate PDF detected: {file.filename}",
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
