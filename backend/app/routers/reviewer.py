"""Reviewer interface: resolve `needs_review` notes.

Protected behind get_reviewer. A reviewer can set a note to accepted or rejected
(with a reject reason). This handles the middle WER band that QC couldn't
auto-classify.
"""
from __future__ import annotations

import datetime as _dt

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..db import get_db
from ..models.voice_note import VoiceNote, VoiceNoteStatus
from ..models.user import User
from ..schemas.voice_note import VoiceNoteListResponse, VoiceNoteOut, ReviewResolveRequest
from ..security.deps import get_reviewer
from ..services.s3 import presigned_get_url

router = APIRouter(prefix="/reviewer", tags=["reviewer"])


def _to_out(note: VoiceNote) -> VoiceNoteOut:
    return VoiceNoteOut(
        id=note.id,
        phrase_text=note.phrase.text if note.phrase else None,
        phrase_id=note.phrase_id,
        whatsapp_message_id=note.whatsapp_message_id,
        duration_seconds=note.duration_seconds,
        mime_type=note.mime_type,
        status=note.status.value if hasattr(note.status, "value") else note.status,
        reject_reason=note.reject_reason,
        qc=note.qc,
        reviewed_at=note.reviewed_at,
        reviewer_id=note.reviewer_id,
        created_at=note.created_at,
        audio_url=presigned_get_url(note.s3_key),
    )


@router.get("/queue", response_model=VoiceNoteListResponse)
async def review_queue(
    user: User = Depends(get_reviewer),
    db: Session = Depends(get_db),
):
    notes = (
        db.query(VoiceNote)
        .filter(VoiceNote.status == VoiceNoteStatus.needs_review)
        .order_by(VoiceNote.created_at.asc())
        .all()
    )
    return VoiceNoteListResponse(items=[_to_out(n) for n in notes], total=len(notes))


@router.get("/all", response_model=VoiceNoteListResponse)
async def review_all(
    status: VoiceNoteStatus | None = Query(None),
    user: User = Depends(get_reviewer),
    db: Session = Depends(get_db),
):
    q = db.query(VoiceNote)
    if status is not None:
        q = q.filter(VoiceNote.status == status)
    notes = q.order_by(VoiceNote.created_at.desc()).all()
    return VoiceNoteListResponse(items=[_to_out(n) for n in notes], total=len(notes))


@router.post("/{note_id}/resolve", response_model=VoiceNoteOut)
async def resolve_note(
    note_id: str,
    body: ReviewResolveRequest,
    user: User = Depends(get_reviewer),
    db: Session = Depends(get_db),
):
    note = db.get(VoiceNote, note_id)
    if not note:
        raise HTTPException(status_code=404, detail="Voice note not found.")
    if note.status != VoiceNoteStatus.needs_review:
        raise HTTPException(status_code=409, detail="Note is not in needs_review.")

    note.status = VoiceNoteStatus(body.status)
    note.reviewed_at = _dt.datetime.now(_dt.timezone.utc)
    note.reviewer_id = user.id
    note.reject_reason = body.reject_reason if body.status == "rejected" else None
    # Stash reviewer info on qc.
    qc = dict(note.qc or {})
    qc["reviewer_id"] = user.id
    qc["reviewed_at"] = note.reviewed_at.isoformat()
    qc["reviewer_status"] = body.status
    note.qc = qc
    db.commit()
    db.refresh(note)
    return _to_out(note)

