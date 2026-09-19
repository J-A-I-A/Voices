"""Portal API: list/inspect the current user's own voice notes.

A user can only ever see and play their own notes. Audio is served through a
short-lived signed S3 URL; we never expose another user's notes.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..db import get_db
from ..models.voice_note import VoiceNote, VoiceNoteStatus
from ..models.user import User
from ..schemas.voice_note import VoiceNoteOut, VoiceNoteListResponse
from ..security.deps import get_verified_user
from ..services.s3 import presigned_get_url

router = APIRouter(prefix="/voice-notes", tags=["voice-notes"])


def _to_out(note: VoiceNote, *, with_url: bool = True) -> VoiceNoteOut:
    out = VoiceNoteOut(
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
        audio_url=presigned_get_url(note.s3_key) if with_url else None,
    )
    return out


@router.get("", response_model=VoiceNoteListResponse)
async def list_my_voice_notes(
    status: VoiceNoteStatus | None = Query(None),
    user: User = Depends(get_verified_user),
    db: Session = Depends(get_db),
):
    q = db.query(VoiceNote).filter(VoiceNote.user_id == user.id)
    if status is not None:
        q = q.filter(VoiceNote.status == status)
    notes = q.order_by(VoiceNote.created_at.desc()).all()
    return VoiceNoteListResponse(
        items=[_to_out(n) for n in notes], total=len(notes)
    )


@router.get("/{note_id}", response_model=VoiceNoteOut)
async def get_my_voice_note(
    note_id: str,
    user: User = Depends(get_verified_user),
    db: Session = Depends(get_db),
):
    note = db.get(VoiceNote, note_id)
    if not note or note.user_id != user.id:
        raise HTTPException(status_code=404, detail="Voice note not found.")
    return _to_out(note)

